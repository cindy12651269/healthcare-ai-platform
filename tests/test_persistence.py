import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from db.models import Base, HealthRecord

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

# Sample Mock Data
def sample_payload():
    return {
        "trace_id": "trace-123",
        "pipeline_version": "v0.1.0",
        "intake": {"text": "headache"},
        "structured_output": {"symptoms": ["headache"]},
        "report_json": {
            "clinical_structuring": {
                "clinical_summary": "Patient reports headache."
            }
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
    assert saved.report_text == "Patient reports headache."
    assert saved.intake_json["text"] == "headache"
    assert saved.structured_output_json["symptoms"] == ["headache"]


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