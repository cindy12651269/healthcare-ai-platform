# Data model v2 (Issue #27) on SQLite: clinics, users, membership roles, clinic-owned
# health records with review status. PostgreSQL migration coverage is in
# tests/test_persistence_postgres.py.
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from db.models import (
    DEFAULT_CLINIC_ID,
    Base,
    Clinic,
    ClinicMembership,
    HealthRecord,
    User,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    # SQLite enforces foreign keys only when asked
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Clinic(id=DEFAULT_CLINIC_ID, name="Default Clinic"))
    s.commit()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        engine.dispose()


def _record(clinic_id=DEFAULT_CLINIC_ID, input_hash="hash-1"):
    return HealthRecord.from_pipeline_trace(
        trace_id="trace-1",
        pipeline_version="v0.1.0",
        intake={"text": "headache"},
        structured_output={"symptoms": ["headache"]},
        report_json={"report_sections": {k: k for k in (
            "overview", "symptom_analysis", "clinical_insights", "risk_summary", "recommendations",
        )}},
        safety_audit={"allowed": True},
        input_hash=input_hash,
        clinic_id=clinic_id,
    )


def test_users_hold_roles_per_clinic(session):
    session.add_all([
        Clinic(id="clinic-b", name="Clinic B"),
        User(id="u1", email="staff@example.test"),
        User(id="u2", email="admin@example.test"),
    ])
    session.flush()
    session.add_all([
        ClinicMembership(user_id="u1", clinic_id=DEFAULT_CLINIC_ID, role="clinic_staff"),
        ClinicMembership(user_id="u2", clinic_id=DEFAULT_CLINIC_ID, role="clinic_admin"),
        ClinicMembership(user_id="u2", clinic_id="clinic-b", role="clinic_staff"),
    ])
    session.commit()

    roles = {(m.user_id, m.clinic_id): m.role for m in session.query(ClinicMembership)}
    assert roles == {
        ("u1", DEFAULT_CLINIC_ID): "clinic_staff",
        ("u2", DEFAULT_CLINIC_ID): "clinic_admin",
        ("u2", "clinic-b"): "clinic_staff",
    }


@pytest.mark.parametrize(
    "rows",
    [
        # unknown role
        lambda: [User(id="u1", email="a@example.test"),
                 ClinicMembership(user_id="u1", clinic_id=DEFAULT_CLINIC_ID, role="superuser")],
        # unknown user
        lambda: [ClinicMembership(user_id="missing", clinic_id=DEFAULT_CLINIC_ID, role="clinic_staff")],
        # duplicate email
        lambda: [User(id="u1", email="a@example.test"), User(id="u2", email="a@example.test")],
    ],
    ids=["invalid-role", "unknown-user", "duplicate-email"],
)
def test_user_and_membership_constraints(session, rows):
    session.add_all(rows())
    with pytest.raises(IntegrityError):
        session.commit()


def test_new_record_is_clinic_owned_and_submitted(session):
    session.add(_record())
    session.commit()

    saved = session.query(HealthRecord).one()
    assert saved.clinic_id == DEFAULT_CLINIC_ID
    assert saved.review_status == "submitted"
    assert saved.escalation_reason is None


def test_review_status_and_escalation_reason_are_stored(session):
    record = _record()
    session.add(record)
    session.commit()

    record.review_status = "escalated"
    record.escalation_reason = "emergency language: chest pain"
    session.commit()

    saved = session.get(HealthRecord, record.id)
    assert (saved.review_status, saved.escalation_reason) == ("escalated", "emergency language: chest pain")


def test_invalid_review_status_is_rejected(session):
    record = _record()
    record.review_status = "closed"
    session.add(record)
    with pytest.raises(IntegrityError):
        session.commit()


def test_record_for_unknown_clinic_is_rejected(session):
    session.add(_record(clinic_id="no-such-clinic"))
    with pytest.raises(IntegrityError):
        session.commit()
