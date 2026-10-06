# Integration test against a real PostgreSQL database: migrations → /api/ingest → health_records row.
# Skipped unless TEST_DATABASE_URL is set, e.g. with the Compose db service running:
#   TEST_DATABASE_URL=postgresql+psycopg2://healthcare_ai:healthcare_ai@localhost:5432/healthcare_ai pytest tests/test_persistence_postgres.py
import os
import shutil
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.migrate import MIGRATIONS_DIR, run_migrations

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(TEST_DATABASE_URL, future=True)
    try:
        with engine.connect():
            pass
    except OperationalError as e:
        pytest.fail(f"TEST_DATABASE_URL is set but PostgreSQL is unreachable: {e}")
    run_migrations(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.setattr(get_settings(), "enable_persistence", True)
    monkeypatch.setattr("agents.pipeline.SessionLocal", sessionmaker(bind=engine, future=True))

    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI client must not be constructed in default mode")

    monkeypatch.setattr("llm.providers.openai_client.OpenAI", _boom)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda event: None)

    get_pipeline.cache_clear()
    yield TestClient(app)
    get_pipeline.cache_clear()


@pytest.fixture
def unique_text(engine):
    text_ = f"I have had a sore throat and a mild fever for two days. Visit ref {uuid4().hex}."
    yield text_
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM health_records WHERE intake_json->>'raw_text' = :t"),
            {"t": text_},
        )


def _ingest(client, text_):
    return client.post(
        "/api/ingest",
        json={"text": text_, "consent_granted": True, "source": "web", "input_type": "intake"},
    )


def test_migrations_create_schema_and_are_idempotent(engine):
    assert run_migrations(engine) == []  # already applied by the fixture

    with engine.connect() as conn:
        applied = conn.execute(text("SELECT filename FROM schema_migrations")).scalars().all()
        column_types = dict(conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'health_records'"
        )).all())

    assert "001_init_health_records.sql" in applied
    assert "002_clinics_users_review_status.sql" in applied
    for column in ("intake_json", "structured_output_json", "report_json", "safety_audit_json"):
        assert column_types[column] == "jsonb"


def test_ingest_persists_record_to_postgres(client, engine, unique_text):
    response = _ingest(client, unique_text)

    assert response.status_code == 200
    data = response.json()
    assert data["persistence"]["status"] == "saved"

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT trace_id, report_json, report_text, structured_output_json, safety_audit_json, "
                "report_json->'report_sections'->>'overview' AS overview, "
                "jsonb_typeof(report_json) AS report_type "
                "FROM health_records WHERE id = :id"
            ),
            {"id": data["persistence"]["record_id"]},
        ).mappings().one()

    assert row["trace_id"] == data["run_id"]
    # JSONB round-trip: stored payloads are queryable objects equal to the API response
    assert row["report_type"] == "object"
    assert row["report_json"] == data["report"]
    assert row["structured_output_json"] == data["structured"]
    assert row["safety_audit_json"] == data["safety"]
    assert row["overview"] == data["report"]["report_sections"]["overview"]
    assert row["report_text"].startswith("overview: ")

    with engine.connect() as conn:
        v2 = conn.execute(
            text("SELECT clinic_id, review_status, escalation_reason FROM health_records WHERE id = :id"),
            {"id": data["persistence"]["record_id"]},
        ).one()
    assert tuple(v2) == ("default", "submitted", None)


def test_identical_input_is_stored_once(client, engine, unique_text):
    first = _ingest(client, unique_text)
    second = _ingest(client, unique_text)

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["persistence"]["status"] == "saved"
    assert second.json()["persistence"] == {"status": "duplicate", "record_id": None}
    assert second.json()["report"]["report_sections"]["overview"]

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM health_records WHERE intake_json->>'raw_text' = :t"),
            {"t": unique_text},
        ).scalar_one()
    assert count == 1


# Data model v2 (Issue #27): each migration test runs in its own throwaway schema

V1_RECORD = {
    "id": "v1-record",
    "trace_id": "v1-trace",
    "intake": '{"raw_text": "v1 intake"}',
    "report": '{"report_sections": {"overview": "v1 overview"}}',
}


@contextmanager
def _isolated_schema(engine):
    schema = f"issue27_{uuid4().hex[:12]}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    scoped = create_engine(TEST_DATABASE_URL, future=True, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))


def _tables_and_columns(conn):
    rows = conn.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema()"
    )).all()
    tables = {}
    for table, column in rows:
        tables.setdefault(table, set()).add(column)
    return tables


def test_fresh_database_migrates_to_v2(engine):
    with _isolated_schema(engine) as scoped:
        assert run_migrations(scoped) == ["001_init_health_records.sql", "002_clinics_users_review_status.sql"]
        assert run_migrations(scoped) == []

        with scoped.connect() as conn:
            tables = _tables_and_columns(conn)
            clinics = conn.execute(text("SELECT id FROM clinics")).scalars().all()

    assert {"clinics", "users", "clinic_memberships", "health_records"} <= set(tables)
    assert {"clinic_id", "review_status", "escalation_reason"} <= tables["health_records"]
    assert {"user_id", "clinic_id", "role"} <= tables["clinic_memberships"]
    assert clinics == ["default"]


def test_v1_database_upgrades_to_v2_without_losing_records(engine, tmp_path):
    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    shutil.copy(MIGRATIONS_DIR / "001_init_health_records.sql", v1_dir)

    with _isolated_schema(engine) as scoped:
        assert run_migrations(scoped, v1_dir) == ["001_init_health_records.sql"]
        with scoped.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO health_records (id, trace_id, pipeline_version, intake_json, "
                    "structured_output_json, report_json, report_text, safety_audit_json, input_hash) "
                    "VALUES (:id, :trace_id, 'v0.1.0', CAST(:intake AS JSONB), '{}'::jsonb, "
                    "CAST(:report AS JSONB), 'overview: v1 overview', '{}'::jsonb, 'v1-hash')"
                ),
                V1_RECORD,
            )

        assert run_migrations(scoped) == ["002_clinics_users_review_status.sql"]

        with scoped.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM health_records WHERE id = :id"), {"id": V1_RECORD["id"]}
            ).mappings().one()
            count = conn.execute(text("SELECT count(*) FROM health_records")).scalar_one()

        assert count == 1
        assert row["trace_id"] == "v1-trace"
        assert row["intake_json"] == {"raw_text": "v1 intake"}
        assert row["report_json"] == {"report_sections": {"overview": "v1 overview"}}
        assert row["input_hash"] == "v1-hash"
        assert (row["clinic_id"], row["review_status"], row["escalation_reason"]) == ("default", "submitted", None)

        # After the backfill, new rows must name their clinic
        with pytest.raises(IntegrityError), scoped.begin() as conn:
            conn.execute(text(
                "INSERT INTO health_records (id, trace_id, pipeline_version, intake_json, "
                "structured_output_json, report_json, report_text, safety_audit_json) "
                "VALUES ('no-clinic', 't', 'v', '{}', '{}', '{}', '', '{}')"
            ))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE health_records SET review_status = 'closed'",
        "UPDATE health_records SET clinic_id = 'no-such-clinic'",
        "INSERT INTO users (id, email) VALUES ('u1', 'a@example.test'); "
        "INSERT INTO clinic_memberships (user_id, clinic_id, role) VALUES ('u1', 'default', 'superuser')",
    ],
    ids=["invalid-review-status", "unknown-clinic", "invalid-role"],
)
def test_v2_constraints_are_enforced(engine, statement):
    with _isolated_schema(engine) as scoped:
        run_migrations(scoped)
        with scoped.begin() as conn:
            conn.execute(text(
                "INSERT INTO health_records (id, trace_id, pipeline_version, intake_json, "
                "structured_output_json, report_json, report_text, safety_audit_json, clinic_id) "
                "VALUES ('r1', 't', 'v', '{}', '{}', '{}', '', '{}', 'default')"
            ))
        with pytest.raises(IntegrityError), scoped.begin() as conn:
            conn.exec_driver_sql(statement)


def test_v2_roles_and_escalation_are_stored(engine):
    with _isolated_schema(engine) as scoped:
        run_migrations(scoped)
        with scoped.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, email) VALUES ('u1', 'staff@example.test'), ('u2', 'admin@example.test');"
                "INSERT INTO clinic_memberships (user_id, clinic_id, role) "
                "VALUES ('u1', 'default', 'clinic_staff'), ('u2', 'default', 'clinic_admin');"
                "INSERT INTO health_records (id, trace_id, pipeline_version, intake_json, "
                "structured_output_json, report_json, report_text, safety_audit_json, clinic_id, "
                "review_status, escalation_reason) "
                "VALUES ('r1', 't', 'v', '{}', '{}', '{}', '', '{}', 'default', 'escalated', 'emergency language')"
            ))
        with scoped.connect() as conn:
            roles = dict(conn.execute(text("SELECT user_id, role FROM clinic_memberships")).all())
            record = conn.execute(text("SELECT review_status, escalation_reason FROM health_records")).one()

    assert roles == {"u1": "clinic_staff", "u2": "clinic_admin"}
    assert tuple(record) == ("escalated", "emergency language")
