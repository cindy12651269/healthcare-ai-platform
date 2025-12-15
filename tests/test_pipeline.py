import pytest
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError
from agents.structuring_agent import StructuringError
from llm.safety_guard import GuardResult


# Mock Agents
class MockStructuringAgent:
    def run(self, intake_dict):
        return {"structured": True}


class MockOutputAgent:
    def run(self, structured_data, retrieval_context=None):
        return {
            "report": {"summary": "ok"},
            "_safety": None,  # pipeline should auto-fill default safety
        }

# SUCCESS: full pipeline
def test_pipeline_success(monkeypatch):
    # Mock intake layer
    class MockIntake:
        def dict(self):
            return {"raw": True}

    def mock_process_raw_input(*args, **kwargs):
        return MockIntake()

    monkeypatch.setattr(
        "agents.pipeline.process_raw_input",
        mock_process_raw_input,
    )

    pipeline = HealthcarePipeline(
        structuring_agent=MockStructuringAgent(),
        output_agent=MockOutputAgent(),
    )

    result = pipeline.run("hello world example input", meta={})

    assert result["success"] is True
    assert result["intake"] == {"raw": True}
    assert result["structured"] == {"structured": True}
    assert result["report"] == {"summary": "ok"}

    # Retrieval is optional in Week 2
    assert result["retrieval_context"] is None

    # Safety trace MUST exist
    assert result["safety"] is not None
    assert result["safety"]["allowed"] is True
    assert result["safety"]["severity"] == "low"

# Intake failure
def test_pipeline_intake_fail(monkeypatch):
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

def test_pipeline_structuring_fail(monkeypatch):
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
        pipeline.run("valid text for intake", meta={})
