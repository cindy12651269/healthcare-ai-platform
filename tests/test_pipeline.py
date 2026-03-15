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


# Pipeline without RAG
def test_pipeline_success_without_rag(monkeypatch):

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

    result = pipeline.run(
        "hello world",
        meta={},
        persistence_enabled=False,
        seed=42,
        run_id="test_no_rag",
    )

    assert result["success"] is True

    assert result["rag"]["enabled"] is False
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

    # telemetry must exist
    assert "telemetry" in result
    assert result["telemetry"]["retrieval_hits"] == 0


# Pipeline with RAG
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

    assert result["success"] is True

    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is True
    assert result["rag"]["chunks"] == ["chunk-1", "chunk-2"]

    assert result["telemetry"]["retrieval_hits"] == 2


# Retrieval failure should be non-fatal
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

    assert result["success"] is True

    assert result["rag"]["enabled"] is True
    assert result["rag"]["used"] is False
    assert result["rag"]["chunks"] == []

    assert result["rag"]["error"] is not None

    assert result["report"] == {"summary": "ok"}

    assert result["telemetry"]["retrieval_hits"] == 0

# Intake failure
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
        pipeline.run(
            "",
            meta={},
            persistence_enabled=False,
            seed=42,
            run_id="test_intake_fail",
        )

# Structuring failure
class FailingStructuringAgent:
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

    with pytest.raises(StructuringError):
        pipeline.run(
            "valid text",
            meta={},
            persistence_enabled=False,
            seed=42,
            run_id="test_struct_fail",
        )