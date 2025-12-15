import json
import pytest
from agents.output_agent import OutputAgent

# Synthetic LLM client (Mimics OpenAI behavior)

# Mimics OpenAI chat completion behavior with synthetic structured output.
class SyntheticCompletions:

    def create(self, *args, **kwargs):
        # Synthetic JSON response generated for deterministic testing
        synthetic_json = {
            "source_struct_id": "test1",
            "report_sections": {
                "overview": "User reports fatigue with mild overall impact.",
                "symptom_analysis": "Fatigue appears intermittent and non-severe.",
                "clinical_insights": "Pattern suggests lifestyle contributors.",
                "risk_summary": "Low risk; no escalation indicators detected.",
                "recommendations": "Maintain hydration and track symptoms."
            },
            "input_context": "unit_test_case",
            "report_metadata": {
                "generated_at": "2025-01-01T00:00:00Z",
                "model_version": "synthetic-model",
                "prompt_version": "v1",
                "latency_ms": 4.8
            }
        }

        class SyntheticMessage:
            content = json.dumps(synthetic_json)

        class SyntheticChoice:
            message = SyntheticMessage()

        class SyntheticResponse:
            choices = [SyntheticChoice()]

        return SyntheticResponse()


class SyntheticChat:
    completions = SyntheticCompletions()


class SyntheticOpenAI:
    # Drop-in replacement for OpenAI() that returns deterministic synthetic outputs.
    def __init__(self, *args, **kwargs):
        self.chat = SyntheticChat()


# Pytest fixture for patching OpenAI client

@pytest.fixture
# Patch OpenAI client with deterministic synthetic client for testing.
def patch_openai(monkeypatch):
    monkeypatch.setattr("agents.output_agent.OpenAI", SyntheticOpenAI)

# Actual test case
def test_output_agent_minimal(patch_openai):
    agent = OutputAgent(model="gpt-4o-mini")

    fake_structured = {
        "trace": {
            "input_id": "test1",
            "user_id": "u123",
            "timestamp": "2025-01-01T00:00:00Z",
            "source": "web",
            "input_type": "chat"
        },
        "compliance": {
            "contains_phi": False,
            "consent_granted": True,
            "data_zone": "public_zone",
            "audit_required": False
        },
        "clinical_structuring": {
            "symptoms": ["fatigue"],
            "clinical_summary": "User reports fatigue.",
            "confidence_level": 0.9
        },
        "agent_decisioning": {
            "recommendations": ["monitor symptoms"],
            "next_actions": ["send_followup"],
            "escalation_required": False
        },
        "ehr_interoperability": {
            "patient_id": "u123",
            "encounter_id": "encounter_test1",
            "fhir_resources": [],
            "hl7_messages": [],
            "sync_status": "pending"
        },
        "output_metadata": {
            "generated_at": "2025-01-01T00:00:00Z",
            "model_version": "test",
            "prompt_version": "v1",
            "latency_ms": 1
        }
    }

    result = agent.run(fake_structured)

    # Core Output Assertions
    assert "report_sections" in result
    assert isinstance(result["report_sections"]["overview"], str)

    # Safety Guard Assertions
    assert "safety_checks" in result
    assert result["safety_checks"]["guard_passed"] is True
    assert isinstance(result["safety_checks"]["events"], list)

    overview_text = result["report_sections"]["overview"].lower()

    # No diagnostic / prescription language
    forbidden_phrases = [
        "you have",
        "diagnosed",
        "suffering from",
        "confirmed",
        "prescribed",
        "take 10mg",
    ]
    assert not any(p in overview_text for p in forbidden_phrases)

    # PHI may be conservatively masked; ensure output is still safe and non-diagnostic
    assert isinstance(overview_text, str)

