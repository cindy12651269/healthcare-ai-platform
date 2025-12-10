import pytest
from unittest.mock import patch
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError
from agents.structuring_agent import StructuringError

# SUCCESS: full pipeline
@patch("agents.output_agent.OutputAgent.run", return_value={"report": "ok"})
@patch("agents.structuring_agent.StructuringAgent.run", return_value={"structured": True})
@patch("agents.intake_agent.IntakeAgent.run", return_value={"raw": True})
@patch("agents.structuring_agent.StructuringAgent.__init__", return_value=None)
@patch("agents.output_agent.OutputAgent.__init__", return_value=None)
def test_pipeline_success(
    mock_out_init,
    mock_struct_init,
    mock_intake,
    mock_struct,
    mock_output,
):
    pipeline = HealthcarePipeline()

    result = pipeline.run("hello world example input", meta={})

    # Original expectations
    assert "structured" in result
    assert "report" in result

    # NEW: pipeline always outputs retrieval_context field
    assert "retrieval_context" in result
    assert result["retrieval_context"] is None

# Intake failure
@patch("agents.intake_agent.IntakeAgent.run", side_effect=IntakeValidationError("bad input"))
@patch("agents.structuring_agent.StructuringAgent.__init__", return_value=None)
@patch("agents.output_agent.OutputAgent.__init__", return_value=None)
def test_pipeline_intake_fail(
    mock_out_init,
    mock_struct_init,
    mock_intake,
):
    pipeline = HealthcarePipeline()

    with pytest.raises(IntakeValidationError):
        pipeline.run("", meta={})

# Structuring failure
@patch("agents.intake_agent.IntakeAgent.run", return_value={"raw": True})
@patch("agents.structuring_agent.StructuringAgent.run", side_effect=StructuringError("struct fail"))
@patch("agents.structuring_agent.StructuringAgent.__init__", return_value=None)
@patch("agents.output_agent.OutputAgent.__init__", return_value=None)
def test_pipeline_structuring_fail(
    mock_out_init,
    mock_struct_init,
    mock_struct_run,
    mock_intake,
):
    pipeline = HealthcarePipeline()

    with pytest.raises(StructuringError):
        pipeline.run("valid text for intake", meta={})
