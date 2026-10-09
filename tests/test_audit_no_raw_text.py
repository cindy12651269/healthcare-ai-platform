# Issue #34: audit events never contain raw intake text.
# Covers the three audit producers — pipeline run events, API request middleware and staff actions (#30) —
# by reading back the JSONL audit file that observability.audit_logger actually writes (redirected to a
# per-test file by tests/conftest.py). Also pins the documented persistence boundary: raw intake text IS
# stored unmasked in health_records.intake_json (docs/security_data_handling.md), but not in audit events.
# Synthetic data only.
import json

import pytest
from fastapi.testclient import TestClient

import observability.audit_logger as audit_logger
from agents.intake_agent import IntakeValidationError
from agents.pipeline import HealthcarePipeline
from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.models import HealthRecord
from tests.test_auth_rbac import auth, sessions  # noqa: F401  (pytest fixture)

# A token that cannot occur in any audit field by chance
SENTINEL = "QXV7731SENTINEL"

EMERGENCY_TEXT = f"Synthetic intake {SENTINEL}: crushing chest pain and trouble breathing since breakfast."
ROUTINE_TEXT = f"Synthetic intake {SENTINEL}: mild sore throat and a runny nose for two days."
# "patient" trips the PHI heuristic; without consent the intake is rejected (failure path)
NO_CONSENT_TEXT = f"Synthetic patient {SENTINEL} reports a dull headache since yesterday evening."


@pytest.fixture
def audit_file(monkeypatch):
    # Real log_run, real JSONL file (path set per test by conftest)
    monkeypatch.setattr(audit_logger, "ENABLE_FILE_LOG", True)
    return audit_logger.JSONL_PATH


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI client must not be constructed in mock mode")

    monkeypatch.setattr("llm.providers.openai_client.OpenAI", _boom)
    monkeypatch.setattr(get_settings(), "webhook_url", None)


def _events(path):
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if line.strip()]
    assert lines, "no audit events were written"
    return lines, [json.loads(line) for line in lines]


def _assert_no_raw_text(lines, *texts):
    for line in lines:
        assert SENTINEL not in line, f"raw intake text leaked into audit event: {line}"
        for text in texts:
            assert text not in line
            assert text.lower() not in line.lower()


def test_pipeline_audit_events_exclude_raw_text_while_record_stores_it(audit_file, mock_mode, sessions, monkeypatch):  # noqa: F811
    monkeypatch.setattr("agents.pipeline.SessionLocal", sessions)
    pipeline = HealthcarePipeline()

    emergency = pipeline.run(EMERGENCY_TEXT, {"consent_granted": True})
    routine = pipeline.run(ROUTINE_TEXT, {"consent_granted": True})
    with pytest.raises(IntakeValidationError):
        pipeline.run(NO_CONSENT_TEXT, {"consent_granted": False})

    lines, events = _events(audit_file)
    _assert_no_raw_text(lines, EMERGENCY_TEXT, ROUTINE_TEXT, NO_CONSENT_TEXT)

    by_run = {e["run_id"]: e for e in events}
    assert by_run[emergency["run_id"]]["status"] == "success"
    assert by_run[emergency["run_id"]]["flags"]["escalation_reasons"] == ["emergency_signal"]
    assert by_run[routine["run_id"]]["status"] == "success"
    failures = [e for e in events if e["status"] == "failure"]
    assert len(failures) == 1 and failures[0]["error"]

    # Persistence boundary (documented, not changed by #34): raw text is stored unmasked in intake_json
    assert emergency["persistence"]["status"] == "saved"
    with sessions() as s:
        stored = s.get(HealthRecord, emergency["persistence"]["record_id"])
        assert stored.intake_json["raw_text"] == EMERGENCY_TEXT
        assert stored.review_status == "needs_review"
        assert SENTINEL not in (stored.escalation_reason or "")


def test_api_middleware_audit_events_exclude_raw_text(audit_file, mock_mode, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_persistence", False)
    get_pipeline.cache_clear()
    client = TestClient(app)
    try:
        ok = client.post("/api/ingest", json={"text": ROUTINE_TEXT, "consent_granted": True})
        rejected = client.post("/api/ingest", json={"text": NO_CONSENT_TEXT, "consent_granted": False})
    finally:
        get_pipeline.cache_clear()

    assert ok.status_code == 200
    assert rejected.status_code == 400

    lines, events = _events(audit_file)
    _assert_no_raw_text(lines, ROUTINE_TEXT, NO_CONSENT_TEXT)

    api_events = [e for e in events if e["run_id"] == "api_request"]
    assert [(e["status"], e["flags"]) for e in api_events] == [
        ("success", {"path": "/api/ingest"}),
        ("failure", {"path": "/api/ingest"}),
    ]
    assert api_events[1]["error"] == "HTTP 400"


def test_staff_action_audit_events_exclude_raw_text(audit_file, sessions):  # noqa: F811
    with sessions() as s:
        s.add(
            HealthRecord(
                id="sentinel-intake",
                trace_id="trace-sentinel",
                pipeline_version="test",
                intake_json={"raw_text": EMERGENCY_TEXT},
                structured_output_json={"clinical_structuring": {"confidence_level": 0.9}},
                report_json={"report_sections": {"overview": "Pre-visit intake received."}},
                report_text="overview: Pre-visit intake received.",
                safety_audit_json={"allowed": True, "actions": [], "reasons": [], "severity": "low"},
                clinic_id="default",
                review_status="needs_review",
                escalation_reason="emergency_signal",
            )
        )
        s.commit()

    client = TestClient(app)
    base = "/api/clinics/default/intakes"
    assert client.get(base, headers=auth("staff-a")).status_code == 200
    detail = client.get(f"{base}/sentinel-intake", headers=auth("staff-a"))
    assert detail.status_code == 200
    transition = client.post(
        f"{base}/sentinel-intake/transition", json={"review_status": "reviewed"}, headers=auth("admin-a")
    )
    assert transition.status_code == 200
    # The staff detail response does not expose intake_json either
    assert SENTINEL not in detail.text and SENTINEL not in transition.text

    lines, events = _events(audit_file)
    _assert_no_raw_text(lines, EMERGENCY_TEXT)

    staff = [(e["actor_id"], e["action"], e["resource_id"]) for e in events if e["action"]]
    assert staff == [
        ("staff-a", "intake.list", None),
        ("staff-a", "intake.read", "sentinel-intake"),
        ("admin-a", "intake.transition", "sentinel-intake"),
    ]
