import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from agents.output_agent import OutputAgent
from agents.pipeline import HealthcarePipeline
from agents.structuring_agent import StructuringAgent
from api.config import get_settings
from db.models import DEFAULT_CLINIC_ID, Base, HealthRecord

# Test DB Setup (In-Memory SQLite)

# Creates isolated in-memory DB session. Rolls back after each test.
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()

# Sample Mock Data (report shaped like llm/schemas/report_output.json)
def sample_payload():
    return {
        "trace_id": "trace-123",
        "pipeline_version": "v0.1.0",
        "intake": {"text": "headache"},
        "structured_output": {"symptoms": ["headache"]},
        "report_json": {
            "source_struct_id": "struct-1",
            "report_sections": {
                "overview": "Patient reports headache.",
                "symptom_analysis": "Symptoms noted: headache.",
                "clinical_insights": "Not a medical assessment.",
                "risk_summary": "No risk scoring.",
                "recommendations": "Track symptoms.",
            },
        },
        "safety_audit": {
            "allowed": True,
            "severity": "low",
            "reasons": [],
        },
        "input_hash": "hash-abc",
    }


# Test 1 — Insert Success
def test_health_record_insert(db_session):
    payload = sample_payload()

    record = HealthRecord.from_pipeline_trace(
        trace_id=payload["trace_id"],
        pipeline_version=payload["pipeline_version"],
        intake=payload["intake"],
        structured_output=payload["structured_output"],
        report_json=payload["report_json"],
        safety_audit=payload["safety_audit"],
        input_hash=payload["input_hash"],
    )

    db_session.add(record)
    db_session.commit()

    saved = db_session.query(HealthRecord).first()

    assert saved is not None
    assert saved.trace_id == "trace-123"
    assert saved.pipeline_version == "v0.1.0"
    assert saved.report_text == (
        "overview: Patient reports headache.\n\n"
        "symptom_analysis: Symptoms noted: headache.\n\n"
        "clinical_insights: Not a medical assessment.\n\n"
        "risk_summary: No risk scoring.\n\n"
        "recommendations: Track symptoms."
    )
    assert saved.intake_json["text"] == "headache"
    assert saved.structured_output_json["symptoms"] == ["headache"]
    assert saved.report_json["report_sections"]["overview"] == "Patient reports headache."


# Test 2 — Unique Constraint (Idempotency)
def test_health_record_unique_input_hash(db_session):
    payload = sample_payload()

    record1 = HealthRecord.from_pipeline_trace(
        trace_id=payload["trace_id"],
        pipeline_version=payload["pipeline_version"],
        intake=payload["intake"],
        structured_output=payload["structured_output"],
        report_json=payload["report_json"],
        safety_audit=payload["safety_audit"],
        input_hash=payload["input_hash"],
    )

    record2 = HealthRecord.from_pipeline_trace(
        trace_id="trace-456",
        pipeline_version="v0.1.0",
        intake=payload["intake"],
        structured_output=payload["structured_output"],
        report_json=payload["report_json"],
        safety_audit=payload["safety_audit"],
        input_hash=payload["input_hash"],  # same hash
    )

    db_session.add(record1)
    db_session.commit()

    db_session.add(record2)

    with pytest.raises(IntegrityError):
        db_session.commit()


# Test 3 — Reports without the required sections are rejected explicitly
@pytest.mark.parametrize(
    "report_json",
    [
        None,
        {"clinical_structuring": {"clinical_summary": "old contract"}},
        {"report_sections": {"overview": "only one section"}},
    ],
)
def test_from_pipeline_trace_rejects_report_without_sections(report_json):
    payload = sample_payload()

    with pytest.raises(ValueError, match="report_sections"):
        HealthRecord.from_pipeline_trace(
            trace_id=payload["trace_id"],
            pipeline_version=payload["pipeline_version"],
            intake=payload["intake"],
            structured_output=payload["structured_output"],
            report_json=report_json,
            safety_audit=payload["safety_audit"],
        )


# Pipeline → save_record regression tests (real deterministic agents, SQLite)

@pytest.fixture
def sqlite_sessions(monkeypatch):
    # One shared in-memory DB across sessions
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("agents.pipeline.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(get_settings(), "enable_persistence", True)
    return TestingSessionLocal


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    return HealthcarePipeline(
        structuring_agent=StructuringAgent(mode="mock"),
        output_agent=OutputAgent(mode="mock"),
    )


META = {"source": "web", "input_type": "intake", "consent_granted": True}


def test_successful_run_persists_current_report_contract(sqlite_sessions, pipeline):
    trace = pipeline.run("I have had a sore throat and a mild fever for two days.", META)

    assert trace["persistence"]["status"] == "saved"
    record_id = trace["persistence"]["record_id"]

    with sqlite_sessions() as session:
        saved = session.get(HealthRecord, record_id)
        assert saved.trace_id == trace["run_id"]
        assert saved.report_json == trace["report"]
        assert saved.structured_output_json == trace["structured"]
        assert saved.safety_audit_json == trace["safety"]
        assert saved.intake_json["input_id"] == trace["intake"]["input_id"]
        assert saved.report_text.startswith("overview: Pre-visit intake received.")
        assert len(saved.input_hash) == 64
        assert saved.clinic_id == DEFAULT_CLINIC_ID
        assert saved.review_status == "submitted"
        assert saved.escalation_reason is None


def test_identical_input_is_reported_as_duplicate(sqlite_sessions, pipeline):
    text = "I have had a sore throat and a mild fever for two days."

    first = pipeline.run(text, META)
    second = pipeline.run(text, META)

    assert first["persistence"]["status"] == "saved"
    assert second["persistence"] == {"status": "duplicate", "record_id": None}
    # The request itself still succeeds
    assert second["success"] is True
    assert second["report"]["report_sections"]["overview"]

    with sqlite_sessions() as session:
        assert session.query(HealthRecord).count() == 1


def test_persistence_disabled_by_settings(sqlite_sessions, pipeline, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    trace = pipeline.run("I have had a sore throat and a mild fever for two days.", META)

    assert trace["persistence"] == {"status": "disabled", "record_id": None}
    with sqlite_sessions() as session:
        assert session.query(HealthRecord).count() == 0


def test_failed_run_is_not_persisted(sqlite_sessions, monkeypatch):
    class ExplodingOutputAgent:
        def run(self, structured_data, retrieval_context=None):
            raise RuntimeError("output exploded")

    pipeline = HealthcarePipeline(
        structuring_agent=StructuringAgent(mode="mock"),
        output_agent=ExplodingOutputAgent(),
    )
    save_results = []
    original = pipeline.save_record
    monkeypatch.setattr(
        pipeline,
        "save_record",
        lambda **kw: save_results.append(original(**kw)) or save_results[-1],
    )

    with pytest.raises(RuntimeError):
        pipeline.run("I have had a sore throat and a mild fever for two days.", META)

    assert save_results == [{"status": "skipped", "record_id": None}]
    with sqlite_sessions() as session:
        assert session.query(HealthRecord).count() == 0


def test_unexpected_db_error_is_reported_and_logged(pipeline, monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "enable_persistence", True)

    class BrokenSession:
        def add(self, record):
            raise RuntimeError("connection refused")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("agents.pipeline.SessionLocal", BrokenSession)

    trace = pipeline.run("I have had a sore throat and a mild fever for two days.", META)

    assert trace["success"] is True
    assert trace["persistence"] == {"status": "failed", "record_id": None}
    assert any(
        r.message == "Persistence failed" and r.exc_info for r in caplog.records
    )
