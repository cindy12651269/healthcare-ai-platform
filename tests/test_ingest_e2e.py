# Unmocked regression test: FastAPI /api/ingest → real HealthcarePipeline → real deterministic agents.
# No OpenAI key is set, and constructing an OpenAI client fails the test.
import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.deps import get_pipeline
from api.main import app

ORIGIN = "http://localhost:3000"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI client must not be constructed in default mode")

    monkeypatch.setattr("agents.output_agent.OpenAI", _boom)
    # Postgres persistence is out of scope here; keep the test hermetic
    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    audit_events = []
    monkeypatch.setattr("api.middleware.audit.log_run", audit_events.append)

    get_pipeline.cache_clear()  # build a fresh real pipeline under these conditions
    test_client = TestClient(app)
    test_client.audit_events = audit_events
    yield test_client
    get_pipeline.cache_clear()


def _ingest(client, text, consent=True):
    return client.post(
        "/api/ingest",
        json={"text": text, "consent_granted": consent, "source": "web", "input_type": "intake"},
        headers={"Origin": ORIGIN},
    )


def test_ingest_succeeds_without_api_key(client):
    response = _ingest(client, "I have had a sore throat and a mild fever for two days.")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    data = response.json()

    assert data["success"] is True
    assert data["errors"] == []

    # Structured result
    clinical = data["structured"]["clinical_structuring"]
    assert clinical["chief_complaint"].startswith("I have had a sore throat")

    # Report consumed by the frontend (app/components/ReportView.tsx)
    report = data["report"]
    assert report is not None
    for key in ("overview", "symptom_analysis", "clinical_insights", "risk_summary", "recommendations"):
        assert report["report_sections"][key]
    assert report["source_struct_id"] == data["intake"]["input_id"]
    assert report["safety_checks"]["diagnostic_check_passed"] is True
    assert report["safety_checks"]["phi_safe"] is True

    # Safety comes from the output-stage guard, not the pipeline default
    assert data["safety"]["allowed"] is True
    assert data["safety"]["severity"] == "low"
    assert data["safety"]["masked_text"]

    # Stage metrics present
    assert data["metrics"]["latency_ms"] >= 0

    assert [e.status for e in client.audit_events] == ["success"]


def test_ingest_propagates_emergency_safety(client):
    response = _ingest(client, "I have chest pain and shortness of breath since this morning.")

    assert response.status_code == 200
    data = response.json()
    assert "add_emergency_guidance" in data["safety"]["actions"]
    assert data["safety"]["severity"] == "high"
    assert "seek urgent medical care" in data["report"]["report_sections"]["overview"]


def test_ingest_masks_phi_in_report(client):
    response = _ingest(client, "Fever for three days, call me at 555-123-4567.")

    assert response.status_code == 200
    data = response.json()
    assert "mask_phi" in data["safety"]["actions"]
    assert "555-123-4567" not in data["report"]["report_sections"]["overview"]


def test_ingest_validation_error_is_cors_visible_and_audited_as_failure(client):
    response = _ingest(client, "short")

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "detail" in response.json()
    assert [e.status for e in client.audit_events] == ["failure"]
    assert client.audit_events[0].error == "HTTP 400"


def test_ingest_phi_without_consent_rejected(client):
    response = _ingest(client, "My phone is 555-123-4567 and I have a cough.", consent=False)

    assert response.status_code == 400
    assert "consent" in response.json()["detail"]
