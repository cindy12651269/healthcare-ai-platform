# Integration test against a real PostgreSQL database: migrations → /api/ingest → health_records row.
# Skipped unless TEST_DATABASE_URL is set, e.g. with the Compose db service running:
#   TEST_DATABASE_URL=postgresql+psycopg2://healthcare_ai:healthcare_ai@localhost:5432/healthcare_ai pytest tests/test_persistence_postgres.py
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.migrate import run_migrations

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
