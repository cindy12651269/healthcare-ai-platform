import pytest
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError
from agents.structuring_agent import StructuringError
from api.config import get_settings

# Mock Agents
class MockStructuringAgent:
    def run(self, intake_dict):
        return {"structured": True}

class MockOutputAgent:
    def run(self, structured_data, retrieval_context=None):
        # Ensure retrieval_context is always safely consumable
        return {
            "report": {"summary": "ok"},
            "_safety": None,
        }

class MockRetrievalAgent:
    def run(self, structured_data, top_k=5):
        return {
            "chunks": ["chunk-1", "chunk-2"],
            "metadata": {}
        }

class FailingRetrievalAgent:
    def run(self, structured_data, top_k=5):
        raise RuntimeError("retrieval exploded")

# Full pipeline (RAG disabled)
# Pipeline should execute normally when RAG is disabled. No retrieval should be executed.
def test_pipeline_success_without_rag(monkeypatch):
    # Disable persistence
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
        retrieval_agent=None,
        enable_retrieval=False,
    )

    result = pipeline.run("hello world", meta={})

    assert result["success"] is True

    # RAG trace must indicate disabled
    assert result["rag"]["enabled"] is False
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

# RAG enabled: When enable_retrieval=True and RetrievalAgent exists,
# retrieval should execute and attach context to trace.
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

    result = pipeline.run("hello world", meta={})

    assert result["success"] is True

    # Retrieval must have been used
    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is True
    assert result["rag"]["chunks"] == ["chunk-1", "chunk-2"]

# Retrieval failure should be NON-FATAL, and must NOT crash pipeline.
# Policy: Retrieval is best-effort. Pipeline should continue without context.
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

    result = pipeline.run("hello world", meta={})

    # Pipeline must still succeed
    assert result["success"] is True

    # Retrieval marked as enabled but NOT used
    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

    # Error must be recorded in RAG trace
    assert result["rag"]["error"] is not None

    # Report must still be generated
    assert result["report"] == {"summary": "ok"}

# Intake failure: Intake validation error must propagate immediately.
def test_pipeline_intake_fail(monkeypatch):

    monkeypatch.setattr(get_settings(), "enable_persistence", False)

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

    with pytest.raises(IntakeValidationError):
        pipeline.run("", meta={})

# Structuring failure
class FailingStructuringAgent:
    def run(self, intake_dict):
        raise StructuringError("struct fail")

# Structuring failure is fatal and must raise.
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

    with pytest.raises(StructuringError):
        pipeline.run("valid text", meta={})