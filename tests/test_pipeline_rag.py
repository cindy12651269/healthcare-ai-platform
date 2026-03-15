import pytest
from agents.pipeline import HealthcarePipeline
from api.config import get_settings

# Mock / Stub Agents
class MockStructuringAgent:
    def run(self, intake_dict):
        return {"chief_complaint": "chest pain", "symptoms": ["shortness of breath"]}


class MockOutputAgent:
    def run(self, structured_data, retrieval_context=None):
        return {
            "report": {"summary": "ok"},
            "_safety": None,
        }


# Deterministic retrieval stub
class StubRetrievalAgent:

    def run(self, structured_data, top_k=3):
        return {
            "query": "chest pain shortness of breath",
            "chunks": [
                {"text": "doc1", "score": 0.91, "source": "kb"},
                {"text": "doc2", "score": 0.88, "source": "kb"},
            ],
        }


class FailingRetrievalAgent:

    def run(self, structured_data, top_k=3):
        raise RuntimeError("retrieval exploded")

# Fixtures
@pytest.fixture(autouse=True)
def disable_persistence(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_persistence", False)


def mock_intake(monkeypatch):

    class MockIntake:
        def dict(self):
            return {"raw": True}

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        lambda *args, **kwargs: MockIntake(),
    )

# RAG Disabled
def test_pipeline_rag_disabled_does_not_call_retrieval(monkeypatch):

    mock_intake(monkeypatch)

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=StubRetrievalAgent(),
        enable_retrieval=False,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="rag_disabled",
    )

    assert result["success"] is True
    assert result["rag"]["enabled"] is False
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []
    assert result["rag"]["error"] is None


# RAG Enabled
def test_pipeline_rag_enabled_includes_trace(monkeypatch):

    mock_intake(monkeypatch)

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=StubRetrievalAgent(),
        enable_retrieval=True,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="rag_enabled",
    )

    assert result["success"] is True
    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is True
    assert len(result["rag"]["chunks"]) == 2
    assert result["rag"]["error"] is None

# Retrieval Failure
def test_pipeline_rag_failure_graceful_degradation(monkeypatch):

    mock_intake(monkeypatch)

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=FailingRetrievalAgent(),
        enable_retrieval=True,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="rag_fail",
    )

    assert result["success"] is True

    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []
    assert result["rag"]["error"] is not None

    assert result["report"] == {"summary": "ok"}


# Output schema still valid
def test_pipeline_rag_output_schema_still_valid(monkeypatch):

    mock_intake(monkeypatch)

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=StubRetrievalAgent(),
        enable_retrieval=True,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="rag_schema",
    )

    assert isinstance(result["report"], dict)
    assert "summary" in result["report"]