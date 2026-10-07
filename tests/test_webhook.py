# Escalation notification webhook (Issue #33): mock-mode pipeline runs with SQLite persistence and a
# recording fake transport. No real outbound HTTP is made.
import json
import socket

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.webhook as webhook
from agents.output_agent import OutputAgent
from agents.pipeline import HealthcarePipeline
from agents.structuring_agent import StructuringAgent
from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.models import Base, HealthRecord, WebhookDelivery

SECRET = "test-webhook-secret-0123456789-abcdefghij"
URL = "https://receiver.example.test/hooks/escalation?token=receiver-path-token"

NORMAL = "I have had a sore throat and a mild fever for two days."
EMERGENCY = "I have chest pain and shortness of breath since this morning."
PRESCRIPTION = "Should I take 500 mg of amoxicillin for this cough?"
DIAGNOSIS = "My neighbour says you have pneumonia, this is confirmed."
# Synthetic PHI that #32 showed survives raw in the trace/safety evidence
PHI_EMERGENCY = "Contact me at jordan.test@example.com, I have chest pain. Patient ID: TEST-0042"
PHI_FRAGMENTS = ("jordan.test@example.com", "TEST-0042", "chest pain", "[PHI_EMAIL]")


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses) or [200]
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append({"url": url, "body": body, "headers": dict(headers), "timeout": timeout})
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, BaseException):
            raise r
        return r


@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("agents.pipeline.SessionLocal", Session)
    monkeypatch.setattr(get_settings(), "enable_persistence", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)
    yield Session
    engine.dispose()


@pytest.fixture
def configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "webhook_url", URL)
    monkeypatch.setattr(settings, "webhook_secret", SECRET)
    monkeypatch.setattr(settings, "webhook_max_attempts", 3)
    monkeypatch.setattr(settings, "webhook_retry_backoff_seconds", 0.5)
    sleeps = []
    monkeypatch.setattr(webhook.time, "sleep", sleeps.append)
    return sleeps


@pytest.fixture
def transport(monkeypatch):
    fake = FakeTransport(200)
    monkeypatch.setattr(webhook, "_post", fake)
    return fake


class LowConfidenceStructuring(StructuringAgent):
    def run(self, health_input):
        out = super().run(health_input)
        out["clinical_structuring"]["confidence_level"] = 0.2
        return out


def _pipeline(structuring=None):
    return HealthcarePipeline(
        structuring_agent=structuring or StructuringAgent(mode="mock"),
        output_agent=OutputAgent(mode="mock"),
    )


def _run(text, structuring=None):
    meta = {"source": "web", "input_type": "intake", "consent_granted": True}
    return _pipeline(structuring).run(raw_text=text, meta=meta, enable_rag=False)


def _deliveries(sessions):
    with sessions() as s:
        return s.query(WebhookDelivery).all()


def _payload(call):
    return json.loads(call["body"])


# Trigger semantics

@pytest.mark.parametrize(
    "text,structuring,reasons",
    [
        (EMERGENCY, None, ["emergency_signal"]),
        (DIAGNOSIS, None, ["blocked_diagnosis"]),
        (PRESCRIPTION, None, ["blocked_prescription"]),
        (NORMAL, LowConfidenceStructuring(mode="mock"), ["low_confidence"]),
    ],
)
def test_each_escalation_trigger_sends_one_notification(sessions, configured, transport, text, structuring, reasons):
    trace = _run(text, structuring)
    assert trace["escalation"]["reasons"] == reasons
    record_id = trace["persistence"]["record_id"]

    assert len(transport.calls) == 1
    assert _payload(transport.calls[0]) == {
        "event": "intake.escalated",
        "schema_version": 1,
        "idempotency_key": f"intake.escalated:{record_id}",
        "intake_id": record_id,
        "clinic_id": "default",
    }
    [delivery] = _deliveries(sessions)
    assert (delivery.status, delivery.attempts, delivery.last_http_status) == ("delivered", 1, 200)


def test_normal_intake_sends_nothing(sessions, configured, transport):
    trace = _run(NORMAL)
    assert trace["persistence"]["status"] == "saved"
    assert trace["escalation"]["required"] is False
    assert transport.calls == []
    assert _deliveries(sessions) == []


def test_multiple_reasons_are_one_logical_notification(sessions, configured, transport):
    trace = _run(EMERGENCY + " " + PRESCRIPTION, LowConfidenceStructuring(mode="mock"))
    assert len(trace["escalation"]["reasons"]) == 3
    assert len(transport.calls) == 1
    assert len(_deliveries(sessions)) == 1


def test_trigger_reads_persisted_status_not_trace(sessions, configured, transport):
    trace = _run(NORMAL)
    record_id = trace["persistence"]["record_id"]
    assert webhook.notify_escalation(record_id, session_factory=sessions)["status"] == "not_escalated"
    assert transport.calls == []


def test_duplicate_submission_and_repeated_handling_do_not_renotify(sessions, configured, transport):
    first = _run(EMERGENCY)
    second = _run(EMERGENCY)  # identical text: existing dedup, no new record
    assert second["persistence"]["status"] == "duplicate"
    assert len(transport.calls) == 1

    again = webhook.notify_escalation(first["persistence"]["record_id"], session_factory=sessions)
    assert again["status"] == "already_notified"
    assert len(transport.calls) == 1
    assert len(_deliveries(sessions)) == 1


# Signature

def test_receiver_verifies_signature_over_exact_bytes(sessions, configured, transport):
    _run(EMERGENCY)
    call = transport.calls[0]
    header = call["headers"][webhook.SIGNATURE_HEADER]

    assert header.startswith("sha256=")
    assert webhook.verify_signature(call["body"], header, SECRET)
    # Independent receiver implementation
    import hashlib
    import hmac
    assert hmac.compare_digest(header, "sha256=" + hmac.new(SECRET.encode(), call["body"], hashlib.sha256).hexdigest())
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"][webhook.EVENT_HEADER] == "intake.escalated"


def test_tampered_payload_or_wrong_secret_fails_verification(sessions, configured, transport):
    _run(EMERGENCY)
    call = transport.calls[0]
    header = call["headers"][webhook.SIGNATURE_HEADER]
    tampered = call["body"].replace(b'"clinic_id":"default"', b'"clinic_id":"other"')

    assert tampered != call["body"]
    assert not webhook.verify_signature(tampered, header, SECRET)
    assert not webhook.verify_signature(call["body"] + b" ", header, SECRET)
    assert not webhook.verify_signature(call["body"], header, SECRET + "x")
    assert not webhook.verify_signature(call["body"], None, SECRET)


# Retries and idempotency

def test_retries_reuse_identical_bytes_signature_and_key_then_stop_on_success(sessions, configured, monkeypatch):
    fake = FakeTransport(503, socket.timeout("timed out"), 200)
    monkeypatch.setattr(webhook, "_post", fake)
    trace = _run(EMERGENCY)

    assert len(fake.calls) == 3
    assert len({c["body"] for c in fake.calls}) == 1
    assert len({c["headers"][webhook.SIGNATURE_HEADER] for c in fake.calls}) == 1
    keys = {c["headers"][webhook.IDEMPOTENCY_HEADER] for c in fake.calls}
    assert keys == {f"intake.escalated:{trace['persistence']['record_id']}"}
    assert configured == [0.5, 1.0]  # deterministic exponential backoff

    [delivery] = _deliveries(sessions)
    assert delivery.status == "delivered" and delivery.attempts == 3 and delivery.delivered_at is not None
    assert [a["outcome"] for a in delivery.attempt_log] == ["http_5xx", "timeout", "delivered"]


def test_exhausted_retries_are_bounded_and_logged(sessions, configured, monkeypatch):
    fake = FakeTransport(ConnectionRefusedError("refused"))
    monkeypatch.setattr(webhook, "_post", fake)
    _run(EMERGENCY)

    assert len(fake.calls) == 3  # webhook_max_attempts
    [delivery] = _deliveries(sessions)
    assert delivery.status == "failed"
    assert delivery.attempts == 3
    assert delivery.last_error == "connection_error"
    assert delivery.last_http_status is None
    assert [a["attempt"] for a in delivery.attempt_log] == [1, 2, 3]


def test_non_retryable_client_error_is_not_retried(sessions, configured, monkeypatch):
    fake = FakeTransport(400)
    monkeypatch.setattr(webhook, "_post", fake)
    _run(EMERGENCY)
    assert len(fake.calls) == 1
    [delivery] = _deliveries(sessions)
    assert (delivery.status, delivery.last_http_status, delivery.last_error) == ("failed", 400, "http_4xx")


def test_delivery_log_holds_non_phi_outcome_metadata(sessions, configured, transport):
    trace = _run(PHI_EMERGENCY)
    [delivery] = _deliveries(sessions)

    assert delivery.idempotency_key == f"intake.escalated:{trace['persistence']['record_id']}"
    assert delivery.intake_id == trace["persistence"]["record_id"]
    assert delivery.event_type == "intake.escalated"
    assert delivery.target == "https://receiver.example.test"  # no path or query token
    assert delivery.created_at is not None and delivery.updated_at is not None

    row = json.dumps({c.name: str(getattr(delivery, c.name)) for c in WebhookDelivery.__table__.columns})
    for fragment in PHI_FRAGMENTS + (SECRET, "receiver-path-token", "sha256="):
        assert fragment not in row


# Patient request isolation

@pytest.mark.parametrize(
    "failure",
    [socket.timeout("timed out"), ConnectionRefusedError("refused"), 500, RuntimeError("transport bug")],
)
def test_webhook_failure_never_fails_patient_ingest(sessions, configured, monkeypatch, failure):
    fake = FakeTransport(failure)
    monkeypatch.setattr(webhook, "_post", fake)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    get_pipeline.cache_clear()
    try:
        response = TestClient(app).post(
            "/api/ingest",
            json={"text": EMERGENCY, "consent_granted": True, "source": "web", "input_type": "intake"},
        )
    finally:
        get_pipeline.cache_clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["persistence"]["status"] == "saved"
    assert data["escalation"]["reasons"] == ["emergency_signal"]
    # The escalated intake stays persisted; nothing about the webhook reaches the patient
    with sessions() as s:
        assert s.get(HealthRecord, data["persistence"]["record_id"]).review_status == "needs_review"
    body = response.text
    for leaked in ("webhook", "intake.escalated", SECRET, "sha256=", "receiver.example.test"):
        assert leaked not in body
    assert len(fake.calls) == 3


def test_database_error_in_notifier_is_contained(sessions, configured, transport):
    def broken_session():
        raise RuntimeError("db down")

    assert webhook.notify_escalation("any", session_factory=broken_session) == {"status": "error"}


# Payload PHI boundary

def test_payload_contains_no_intake_report_or_safety_evidence(sessions, configured, transport):
    trace = _run(PHI_EMERGENCY)
    # #32 finding: raw PHI is present in these trace locations
    assert "jordan.test@example.com" in trace["intake"]["raw_text"]
    assert "jordan.test@example.com" in json.dumps(trace["safety"]["reasons"])
    assert "jordan.test@example.com" in trace["structured"]["clinical_structuring"]["chief_complaint"]

    call = transport.calls[0]
    body = call["body"].decode()
    assert set(_payload(call)) == {"event", "schema_version", "idempotency_key", "intake_id", "clinic_id"}
    for fragment in PHI_FRAGMENTS + ("raw_text", "chief_complaint", "report", "safety", "match", "reasons", "trace"):
        assert fragment not in body
    for value in call["headers"].values():
        for fragment in PHI_FRAGMENTS:
            assert fragment not in value


def test_payload_model_forbids_extra_fields():
    with pytest.raises(ValidationError):
        webhook.EscalationPayload(
            event="intake.escalated",
            schema_version=1,
            idempotency_key="k",
            intake_id="i",
            clinic_id="c",
            raw_text="should not be accepted",
        )


def test_secret_never_in_payload_headers_or_logs(sessions, configured, transport, caplog):
    caplog.set_level("DEBUG")
    _run(EMERGENCY)
    call = transport.calls[0]
    assert SECRET.encode() not in call["body"]
    assert all(SECRET not in v for v in call["headers"].values())
    assert SECRET not in caplog.text
    assert call["headers"][webhook.SIGNATURE_HEADER] not in caplog.text
    assert "receiver-path-token" not in caplog.text


# Configuration

@pytest.mark.parametrize(
    "url,secret",
    [(None, None), (URL, None), (None, SECRET), (URL, "too-short"), ("ftp://receiver.example.test", SECRET)],
)
def test_missing_or_invalid_config_disables_webhook_safely(sessions, monkeypatch, transport, url, secret):
    monkeypatch.setattr(get_settings(), "webhook_url", url)
    monkeypatch.setattr(get_settings(), "webhook_secret", secret)
    trace = _run(EMERGENCY)

    assert trace["success"] is True
    assert trace["persistence"]["status"] == "saved"
    assert transport.calls == []
    assert _deliveries(sessions) == []
    assert webhook.notify_escalation(trace["persistence"]["record_id"], session_factory=sessions) == {"status": "disabled"}


def test_no_persistence_means_no_notification(monkeypatch, configured, transport):
    monkeypatch.setattr(get_settings(), "enable_persistence", False)
    trace = _run(EMERGENCY)
    assert trace["persistence"]["status"] == "disabled"
    assert transport.calls == []


# Real urllib transport against a loopback receiver (no external network)
def test_real_transport_receiver_verifies_received_bytes(sessions, configured, monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((body, dict(self.headers)))
            self.send_response(204 if webhook.verify_signature(body, self.headers[webhook.SIGNATURE_HEADER], SECRET) else 401)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(get_settings(), "webhook_url", f"http://127.0.0.1:{server.server_port}/hook")
    try:
        trace = _run(EMERGENCY)
    finally:
        server.shutdown()

    [(body, headers)] = received
    assert json.loads(body)["intake_id"] == trace["persistence"]["record_id"]
    assert headers[webhook.IDEMPOTENCY_HEADER] == f"intake.escalated:{trace['persistence']['record_id']}"
    [delivery] = _deliveries(sessions)
    assert (delivery.status, delivery.last_http_status) == ("delivered", 204)
