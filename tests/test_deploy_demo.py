# Hosted demo readiness (Issue #35): Render Blueprint configuration, deterministic demo seed, and the
# hosted acceptance flow (flagged intake -> correct clinic's review queue -> signed webhook) run
# in-process through scripts/hosted_check.py against SQLite and a loopback webhook receiver.
# This proves deployment readiness only; it is not a verification of the hosted environment.
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml  # PyYAML ships with uvicorn[standard] (requirements.txt)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import webhook
from api.auth import issue_token
from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.models import Base, Clinic, ClinicMembership, User, WebhookDelivery
from db.seed_demo import DEMO_USERS, seed_demo
from db.session import get_db
from scripts import hosted_check, verify_webhook

ROOT = Path(__file__).resolve().parent.parent
AUTH_SECRET = "deploy-test-auth-" + "x" * 40
WEBHOOK_SECRET = "deploy-test-webhook-" + "y" * 40
SECRET_KEY = re.compile(r"SECRET|PASSWORD|API_KEY|TOKEN|DATABASE_URL", re.I)


# Render Blueprint

@pytest.fixture(scope="module")
def blueprint():
    return yaml.safe_load((ROOT / "render.yaml").read_text())


def _service(blueprint, name):
    [svc] = [s for s in blueprint["services"] if s["name"] == name]
    return svc, {e["key"]: e for e in svc.get("envVars", [])}


def test_api_service_migrates_seeds_and_health_checks(blueprint):
    api, _ = _service(blueprint, "healthcare-ai-api")
    assert api["dockerCommand"] == "sh scripts/start_api.sh"
    lines = [l.strip() for l in (ROOT / "scripts" / "start_api.sh").read_text().splitlines()]
    steps = [l for l in lines if l and not l.startswith("#")]

    assert api["runtime"] == "docker" and api["dockerfilePath"] == "./Dockerfile"
    assert api["healthCheckPath"] == "/health"
    # Order matters, and set -e makes a failed migration or seed stop the start
    assert steps[0] == "set -e"
    assert steps[1:3] == ["python -m db.migrate", "python -m db.seed_demo"]
    assert steps[3].startswith("exec uvicorn api.main:app --host 0.0.0.0") and "--reload" not in steps[3]


def test_api_service_defaults_to_mock_and_keeps_secrets_out_of_the_file(blueprint):
    _, env = _service(blueprint, "healthcare-ai-api")

    assert env["LLM_MODE"]["value"] == "mock"
    assert "OPENAI_API_KEY" not in env  # real mode needs explicit configuration in the dashboard
    assert env["DATABASE_URL"]["fromDatabase"] == {"name": "healthcare-ai-db", "property": "connectionString"}
    for key in ("AUTH_TOKEN_SECRET", "WEBHOOK_SECRET"):
        assert env[key] == {"key": key, "generateValue": True}
    for key, spec in env.items():
        if SECRET_KEY.search(key):
            assert "value" not in spec, f"{key} must not have a literal value in render.yaml"


def test_frontend_receives_no_backend_secrets(blueprint):
    frontend, env = _service(blueprint, "healthcare-ai-frontend")

    assert frontend["dockerContext"] == "./app" and frontend["healthCheckPath"] == "/"
    assert set(env) == {"PORT", "NEXT_PUBLIC_API_BASE_URL"}
    assert env["NEXT_PUBLIC_API_BASE_URL"] == {"key": "NEXT_PUBLIC_API_BASE_URL", "sync": False}
    # The only browser-visible variable the UI reads
    sources = [p for d in ("components", "pages", "services") for p in (ROOT / "app" / d).rglob("*.ts*")]
    public = {m for p in sources for m in re.findall(r"process\.env\.(\w+)", p.read_text())}
    assert public == {"NEXT_PUBLIC_API_BASE_URL"}


def test_single_free_database_and_two_services(blueprint):
    assert [s["name"] for s in blueprint["services"]] == ["healthcare-ai-api", "healthcare-ai-frontend"]
    assert [(d["name"], d["plan"]) for d in blueprint["databases"]] == [("healthcare-ai-db", "free")]
    assert {s["plan"] for s in blueprint["services"]} == {"free"}


# Demo seed + in-process acceptance flow

@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        s.add(Clinic(id="default", name="Default Clinic"))  # as migration 002 does
        s.commit()

    def _get_db():
        db = Session()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield Session
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_seed_is_deterministic_and_idempotent(sessions):
    with sessions() as s:
        first = seed_demo(s)
        s.commit()
    with sessions() as s:
        assert seed_demo(s) == []
        s.commit()

    assert "clinic default" not in first  # the migration already created it
    with sessions() as s:
        assert {c.id for c in s.query(Clinic)} == {"default", "demo-clinic-b"}
        assert {u.id for u in s.query(User)} == {u[0] for u in DEMO_USERS}
        assert all(u.email.endswith("@demo.example.test") for u in s.query(User))
        assert {(m.user_id, m.clinic_id, m.role) for m in s.query(ClinicMembership)} == {
            ("demo-staff-a", "default", "clinic_staff"),
            ("demo-admin-a", "default", "clinic_admin"),
            ("demo-admin-b", "demo-clinic-b", "clinic_admin"),
        }


@pytest.fixture
def receiver():
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.rfile.read(int(self.headers["Content-Length"])), dict(self.headers)))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/hook", received
    server.shutdown()


def _testclient_http(client):
    def call(method, path, token=None, body=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, path, headers=headers, json=body)
        return response.status_code, (response.json() if response.content else None)

    return call


def test_acceptance_flow_flagged_intake_reaches_clinic_queue_and_signed_webhook(
    sessions, receiver, monkeypatch, tmp_path
):
    url, received = receiver
    settings = get_settings()
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "auth_token_secret", AUTH_SECRET)
    monkeypatch.setattr(settings, "webhook_url", url)
    monkeypatch.setattr(settings, "webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "webhook_retry_backoff_seconds", 0)
    monkeypatch.setattr(settings, "enable_persistence", True)
    monkeypatch.setattr("agents.pipeline.SessionLocal", sessions)
    with sessions() as s:
        seed_demo(s)
        s.commit()

    get_pipeline.cache_clear()
    try:
        lines = []
        intake_id = hosted_check.run(
            _testclient_http(TestClient(app)),
            issue_token("demo-staff-a", 600),
            issue_token("demo-admin-b", 600),
            log=lines.append,
        )
    finally:
        get_pipeline.cache_clear()

    assert intake_id, "\n".join(lines)
    assert not any(line.startswith("[FAIL]") for line in lines)

    # Exactly one signed delivery for this intake; verified with the operator script
    [(body, headers)] = received
    assert json.loads(body) == {
        "event": "intake.escalated",
        "schema_version": 1,
        "idempotency_key": f"intake.escalated:{intake_id}",
        "intake_id": intake_id,
        "clinic_id": "default",
    }
    body_file = tmp_path / "body.json"
    body_file.write_bytes(body)
    monkeypatch.setenv("WEBHOOK_SECRET", WEBHOOK_SECRET)
    signature = headers[webhook.SIGNATURE_HEADER]
    assert verify_webhook.main(["--body-file", str(body_file), "--signature", signature]) == 0
    assert verify_webhook.main(["--body-file", str(body_file), "--signature", "sha256=" + "0" * 64]) == 1

    with sessions() as s:
        [delivery] = s.query(WebhookDelivery).all()
        assert (delivery.intake_id, delivery.status) == (intake_id, "delivered")


def test_hosted_check_fails_when_isolation_is_broken():
    # Clinic B can read clinic A's intake: the check must report failure
    def http(method, path, token=None, body=None):
        if path == "/health":
            return 200, {"status": "ok", "llm_mode": "mock"}
        if path == "/api/ingest":
            return 200, {"escalation": {"review_status": "needs_review"}, "persistence": {"status": "saved", "record_id": "r1"}}
        if path.endswith("/intakes/r1"):
            return 200, {"id": "r1"}
        if "demo-clinic-b" in path:
            return 200, []
        return 200, [{"id": "r1"}]

    lines = []
    assert hosted_check.run(http, "a", "b", log=lines.append) is None
    assert "[FAIL] clinic B denied clinic A intake (HTTP 200)" in lines
