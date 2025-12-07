import pytest
from fastapi.testclient import TestClient
from api.main import app
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError

import os
os.environ["OPENAI_API_KEY"] = "dummy"

client = TestClient(app)

@pytest.fixture(autouse=True)
# Mock pipeline.run() so tests don't require OpenAI or full LLM stack.
def mock_pipeline(monkeypatch):

    def fake_run(self, raw_text, meta):
        # Let test_ingest_empty_text work normally
        if raw_text == "":
            
            raise IntakeValidationError("raw_text cannot be empty.")

        # Normal simulated success
        return {
            "success": True,
            "intake": {"raw_text": raw_text},
            "structured": {"symptoms": ["fatigue", "chest tightness"]},
            "report": {"summary": "dummy report"},
            "errors": []
        }

    monkeypatch.setattr(HealthcarePipeline, "run", fake_run)

# Actual tests
# Test successful ingestion
def test_ingest_success():
    payload = {
        "text": "Feeling chest tightness and fatigue for 3 days.",
        "source": "web",
        "input_type": "chat",
        "consent_granted": True,
        "user_id": "test-user-123"
    }

    response = client.post("/api/ingest", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["intake"] is not None
    assert data["structured"] is not None
    assert data["report"] is not None
    assert isinstance(data["errors"], list)

# Test ingestion with missing required field 'text'
def test_ingest_missing_text():
    payload = {
        "source": "web",
        "consent_granted": True,
        "input_type": "chat",
    }

    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 422  # FastAPI validation error

# Test ingestion with empty text
def test_ingest_empty_text():
    payload = {
        "text": "",
        "source": "web",
        "input_type": "chat",
        "consent_granted": True
    }

    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 400
    assert "detail" in response.json()


