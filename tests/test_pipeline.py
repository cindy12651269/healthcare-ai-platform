import pytest
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError
from agents.structuring_agent import StructuringError
from api.config import get_settings
from agents.retrieval_agent import RetrievalResult, RetrievalChunk


# Mock Agents (Test Doubles)
class MockStructuringAgent:
    # Always returns a valid structured output
    def run(self, intake_dict):
        return {"structured": True}

class MockOutputAgent:
    # Always returns a valid report with no safety violations
    def run(self, structured_data, retrieval_context=None):
        return {
            "report": {"summary": "ok"},
            "_safety": None,
        }


class MockRetrievalAgent:
    def run(self, structured_data, top_k=5):
        chunks = [
            RetrievalChunk(text="chunk-1", source=None, score=None),
            RetrievalChunk(text="chunk-2", source=None, score=None),
        ]
        return RetrievalResult(
            query="test-query",
            chunks=chunks,
            k=top_k,
            hit_count=2,
        )


class FailingRetrievalAgent:
    # Simulates retrieval failure
    def run(self, structured_data, top_k=5):
        raise RuntimeError("retrieval exploded")

# Success without RAG
def test_pipeline_success_without_rag(monkeypatch):

    # Disable persistence for deterministic testing
    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    class MockIntake:
        def dict(self):
            return {"raw": True}

    # Mock intake step
    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        lambda *args, **kwargs: MockIntake(),
    )

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=None,
        enable_retrieval=False,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="test_no_rag",
    )

    # Validate pipeline success
    assert result["success"] is True

    # Validate RAG behavior
    assert result["rag"]["enabled"] is False
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

    # Validate telemetry
    assert "telemetry" in result
    assert result["telemetry"]["retrieval_hits"] == 0
    assert "metrics" in result
    assert "latency_ms" in result["metrics"]   


# Success with RAG
def test_pipeline_success_with_rag(monkeypatch):

    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    class MockIntake:
        def dict(self):
            return {"raw": True}

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        lambda *args, **kwargs: MockIntake(),
    )

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
        retrieval_agent=MockRetrievalAgent(),
        enable_retrieval=True,
    )

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="test_with_rag",
    )

    # Validate success
    assert result["success"] is True

    # Validate RAG execution
    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is True
    assert result["rag"]["chunks"] == ["chunk-1", "chunk-2"]

    # Validate telemetry
    assert result["telemetry"]["retrieval_hits"] == 2
    assert "metrics" in result
    assert "latency_ms" in result["metrics"]

# Retrieval failure (non-fatal)
def test_pipeline_rag_failure_non_fatal(monkeypatch):

    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    class MockIntake:
        def dict(self):
            return {"raw": True}

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        lambda *args, **kwargs: MockIntake(),
    )

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
        run_id="test_rag_fail",
    )

    # Pipeline should still succeed
    assert result["success"] is True

    # RAG failure should not crash pipeline
    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

    # Error should be recorded
    assert result["rag"]["error"] is not None

    # Output should still exist
    assert result["report"] == {"summary": "ok"}

    # Telemetry should still be correct
    assert result["telemetry"]["retrieval_hits"] == 0
    assert "metrics" in result
    assert "latency_ms" in result["metrics"]


# Intake failure
def test_pipeline_intake_fail(monkeypatch):

    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    # Force intake to fail
    def mock_process_raw_input(*args, **kwargs):
        raise IntakeValidationError("bad input")

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        mock_process_raw_input,
    )

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
    )

    # Pipeline should raise intake error
    with pytest.raises(IntakeValidationError):
        pipeline.run(
            "",
            meta={},
            persistence_enabled=False,
            seed=42,
            run_id="test_intake_fail",
        )

# Structuring failure
class FailingStructuringAgent:
    # Always fails structuring
    def run(self, intake_dict):
        raise StructuringError("struct fail")


def test_pipeline_structuring_fail(monkeypatch):

    monkeypatch.setattr(get_settings(), "enable_persistence", False)

    class MockIntake:
        def dict(self):
            return {"raw": True}

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        lambda *args, **kwargs: MockIntake(),
    )

    pipeline = HealthcarePipeline(
        structuring_agent=FailingStructuringAgent(),
        output_agent=MockOutputAgent(),
    )

    # Pipeline should raise structuring error
    with pytest.raises(StructuringError):
        pipeline.run(
            "valid text",
            meta={},
            persistence_enabled=False,
            seed=42,
            run_id="test_struct_fail",
        )
