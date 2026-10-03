import pytest
from agents.output_agent import OutputAgent
from llm.safety_guard import GuardResult


# Any attempt to build a provider client in mock mode fails the test
@pytest.fixture(autouse=True)
def forbid_openai(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI client must not be constructed in mock mode")

    monkeypatch.setattr("agents.output_agent.OpenAI", _boom)
    monkeypatch.delenv("LLM_MODE", raising=False)


def _structured(chief_complaint: str, input_id: str = "3f2a1b9c-8935-5138-8867-0242ac120002"):
    return {
        "trace": {"input_id": input_id, "input_type": "intake"},
        "compliance": {"consent_granted": True},
        "clinical_structuring": {
            "chief_complaint": chief_complaint,
            "symptoms": [],
            "clinical_summary": "mock summary",
            "confidence_level": 0.9,
        },
        "agent_decisioning": {},
        "ehr_interoperability": {},
        "output_metadata": {"generated_at": "2025-01-01T00:00:00Z"},
    }


# Default mode is mock and needs no provider client
def test_default_mode_is_mock_without_client():
    agent = OutputAgent()
    assert agent.mode == "mock"
    assert agent.client is None


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        OutputAgent(mode="bogus")


# Mock output follows the pipeline contract and the report schema
def test_mock_run_returns_pipeline_contract():
    out = OutputAgent().run(_structured("Sore throat and mild fever for two days."))

    assert set(out) == {"report", "_safety"}
    report = out["report"]
    assert set(report["report_sections"]) == {
        "overview", "symptom_analysis", "clinical_insights", "risk_summary", "recommendations",
    }
    assert "Sore throat and mild fever" in report["report_sections"]["overview"]
    assert report["report_metadata"]["model_version"] == "mock"
    assert report["safety_checks"]["diagnostic_check_passed"] is True
    assert report["safety_checks"]["phi_safe"] is True

    assert isinstance(out["_safety"], GuardResult)
    assert out["_safety"].allowed is True
    assert out["_safety"].severity == "low"


# Same input → same report
def test_mock_run_is_deterministic():
    a = OutputAgent().run(_structured("Headache since Monday morning."))
    b = OutputAgent().run(_structured("Headache since Monday morning."))
    assert a["report"] == b["report"]
    assert a["_safety"].to_dict() == b["_safety"].to_dict()


# Identifiers are not run through PHI masking (UUID digit runs used to match the phone regex)
def test_identifiers_not_masked():
    input_id = "89355138-8867-4c1e-9d55-0242ac120002"
    out = OutputAgent().run(_structured("Sore throat for two days.", input_id=input_id))
    assert out["report"]["source_struct_id"] == input_id
    assert out["report"]["safety_checks"]["phi_safe"] is True


# Emergency language propagates to the aggregated guard result
def test_emergency_guidance_propagates():
    out = OutputAgent().run(_structured("I have chest pain and shortness of breath."))
    assert "add_emergency_guidance" in out["_safety"].actions
    assert out["_safety"].severity == "high"
    assert "seek urgent medical care" in out["report"]["report_sections"]["overview"]


# PHI in echoed text is masked and reported
def test_phi_masked_and_reported():
    out = OutputAgent().run(_structured("Fever for 3 days, call me at 555-123-4567."))
    assert "555-123-4567" not in out["report"]["report_sections"]["overview"]
    assert "mask_phi" in out["_safety"].actions
    assert out["report"]["safety_checks"]["phi_safe"] is False


# Blocking behaviour is unchanged: diagnostic certainty still blocks the report
def test_diagnostic_content_still_blocked():
    with pytest.raises(ValueError, match="blocked"):
        OutputAgent().run(_structured("You have pneumonia, this is confirmed."))
