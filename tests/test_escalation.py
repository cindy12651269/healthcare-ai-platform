# Escalation rules (Issue #29): unit tests for the rules, and mock-mode end-to-end runs
# through the real pipeline with SQLite persistence and captured audit events.
import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import validate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.escalation import LOW_CONFIDENCE_THRESHOLD, evaluate_escalation
from agents.output_agent import OutputAgent
from agents.pipeline import HealthcarePipeline
from agents.structuring_agent import StructuringAgent
from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.models import Base, HealthRecord
from llm.safety_guard import EMERGENCY_GUIDANCE

NORMAL = "I have had a sore throat and a mild fever for two days."
EMERGENCY = "I have chest pain and shortness of breath since this morning."
# Mock reports echo the complaint, so these make the generated report trip the guard's hard blocks
DIAGNOSIS = "My neighbour says you have pneumonia, this is confirmed."
PRESCRIPTION = "Should I take 500 mg of amoxicillin for this cough?"
BLOCKED_FRAGMENTS = ("pneumonia", "confirmed", "500 mg", "amoxicillin")


def _structured(confidence):
    return {"clinical_structuring": {"confidence_level": confidence}}


# Unit: rules

def test_no_trigger_keeps_initial_status():
    decision = evaluate_escalation(intake_text=NORMAL, structured=_structured(0.9), safety_actions=[])
    assert decision["required"] is False
    assert decision["review_status"] == "submitted"
    assert decision["reasons"] == []


def test_each_trigger_maps_to_its_reason():
    cases = [
        ({"safety_actions": ["add_emergency_guidance"]}, ["emergency_signal"]),
        ({"safety_actions": ["block_diagnosis"]}, ["blocked_diagnosis"]),
        ({"safety_actions": ["block_prescription"]}, ["blocked_prescription"]),
    ]
    for kwargs, reasons in cases:
        decision = evaluate_escalation(intake_text=NORMAL, structured=_structured(0.9), **kwargs)
        assert decision["review_status"] == "needs_review"
        assert decision["reasons"] == reasons


def test_emergency_signal_in_intake_text_escalates():
    decision = evaluate_escalation(intake_text=EMERGENCY, structured=_structured(0.9), safety_actions=[])
    assert decision["reasons"] == ["emergency_signal"]


def test_low_confidence_threshold_is_strict():
    below = evaluate_escalation(
        intake_text=NORMAL, structured=_structured(LOW_CONFIDENCE_THRESHOLD - 0.01), safety_actions=[]
    )
    at = evaluate_escalation(
        intake_text=NORMAL, structured=_structured(LOW_CONFIDENCE_THRESHOLD), safety_actions=[]
    )
    assert below["reasons"] == ["low_confidence"]
    assert at["required"] is False


def test_multiple_reasons_are_all_recorded():
    decision = evaluate_escalation(
        intake_text=EMERGENCY,
        structured=_structured(0.1),
        safety_actions=["block_diagnosis", "block_prescription"],
    )
    assert decision["reasons"] == [
        "emergency_signal",
        "blocked_diagnosis",
        "blocked_prescription",
        "low_confidence",
    ]


# End-to-end (mock mode)

@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("agents.pipeline.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(get_settings(), "enable_persistence", True)
    return TestingSessionLocal


@pytest.fixture
def audit_events(monkeypatch):
    events = []
    monkeypatch.setattr("agents.pipeline.log_run", events.append)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    return events


@pytest.fixture
def client(monkeypatch, sessions, audit_events):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)
    get_pipeline.cache_clear()
    yield TestClient(app)
    get_pipeline.cache_clear()


def _ingest(client, text):
    response = client.post(
        "/api/ingest",
        json={"text": text, "consent_granted": True, "source": "web", "input_type": "intake"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _saved(sessions, data):
    assert data["persistence"]["status"] == "saved"
    with sessions() as session:
        return session.get(HealthRecord, data["persistence"]["record_id"])


def _assert_trace_and_audit_safe(data, audit_events, text, reasons):
    assert data["escalation"]["reasons"] == reasons
    event = audit_events[-1]
    assert event.status == "success"
    assert event.flags["escalation_required"] is bool(reasons)
    assert event.flags["escalation_reasons"] == reasons
    serialized_event = json.dumps(event.__dict__)
    serialized_decision = json.dumps(data["escalation"])
    assert text not in serialized_event
    assert text not in serialized_decision


def test_normal_intake_is_not_escalated(client, sessions, audit_events):
    data = _ingest(client, NORMAL)

    assert data["escalation"]["required"] is False
    record = _saved(sessions, data)
    assert record.review_status == "submitted"
    assert record.escalation_reason is None
    _assert_trace_and_audit_safe(data, audit_events, NORMAL, [])


def test_emergency_intake_needs_review_and_guidance_unchanged(client, sessions, audit_events):
    data = _ingest(client, EMERGENCY)

    record = _saved(sessions, data)
    assert record.review_status == "needs_review"
    assert record.escalation_reason == "emergency_signal"
    # Patient-facing report is the normal guarded report with the unchanged guidance text
    overview = data["report"]["report_sections"]["overview"]
    assert overview.endswith("\n\n" + EMERGENCY_GUIDANCE)
    assert data["report"]["report_metadata"]["model_version"] == "mock"
    _assert_trace_and_audit_safe(data, audit_events, EMERGENCY, ["emergency_signal"])


@pytest.mark.parametrize(
    "text, reason",
    [(DIAGNOSIS, "blocked_diagnosis"), (PRESCRIPTION, "blocked_prescription")],
)
def test_blocked_output_returns_controlled_acknowledgement(client, sessions, audit_events, text, reason):
    data = _ingest(client, text)

    assert data["success"] is True
    assert data["errors"] == []

    report = data["report"]
    validate(instance=report, schema=json.loads(open("llm/schemas/report_output.json").read()))
    assert report["report_metadata"]["model_version"] == "safety_acknowledgement"
    assert report["safety_checks"]["diagnostic_check_passed"] is False
    assert "received" in report["report_sections"]["overview"]

    # No blocked content in anything derived from the generated report
    assert data["safety"]["allowed"] is False
    assert data["safety"]["masked_text"] == ""
    assert f"block_{reason.split('_')[1]}" in data["safety"]["actions"]
    exposed = json.dumps([report, data["safety"], data["escalation"]])
    for fragment in BLOCKED_FRAGMENTS:
        assert fragment not in exposed

    record = _saved(sessions, data)
    assert record.review_status == "needs_review"
    assert record.escalation_reason == reason
    assert record.report_json == report
    _assert_trace_and_audit_safe(data, audit_events, text, [reason])


def test_blocked_output_with_emergency_keeps_guidance(sessions, audit_events, monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    pipeline = HealthcarePipeline(structuring_agent=StructuringAgent(mode="mock"), output_agent=OutputAgent(mode="mock"))
    text = "You have a stroke, this is confirmed, I fainted earlier."

    trace = pipeline.run(text, {"source": "web", "input_type": "intake", "consent_granted": True})

    assert trace["escalation"]["reasons"] == ["emergency_signal", "blocked_diagnosis"]
    assert trace["report"]["report_sections"]["overview"].endswith("\n\n" + EMERGENCY_GUIDANCE)
    assert "confirmed" not in json.dumps(trace["report"])
    assert _saved(sessions, trace).escalation_reason == "emergency_signal,blocked_diagnosis"


def test_low_confidence_intake_needs_review(sessions, audit_events, monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    struct = StructuringAgent(mode="mock")
    original = struct.run

    def low_confidence_run(health_input):
        out = original(health_input)
        out["clinical_structuring"]["confidence_level"] = 0.2
        return out

    struct.run = low_confidence_run
    pipeline = HealthcarePipeline(structuring_agent=struct, output_agent=OutputAgent(mode="mock"))

    trace = pipeline.run(NORMAL, {"source": "web", "input_type": "intake", "consent_granted": True})

    record = _saved(sessions, trace)
    assert record.review_status == "needs_review"
    assert record.escalation_reason == "low_confidence"
    assert trace["escalation"]["confidence_level"] == 0.2
    _assert_trace_and_audit_safe(trace, audit_events, NORMAL, ["low_confidence"])
