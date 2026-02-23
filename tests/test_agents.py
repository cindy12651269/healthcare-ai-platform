import json
import pytest
from agents.output_agent import OutputAgent


# Synthetic OpenAI mock
class SyntheticCompletions:
    def create(self, *args, **kwargs):
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
    def __init__(self, *args, **kwargs):
        self.chat = SyntheticChat()


@pytest.fixture
def patch_openai(monkeypatch):
    monkeypatch.setattr("agents.output_agent.OpenAI", SyntheticOpenAI)


def test_output_agent_minimal(patch_openai):
    agent = OutputAgent(model="gpt-4o-mini")

    fake_structured = {
        "trace": {"input_id": "test1"},
        "compliance": {"consent_granted": True},
        "clinical_structuring": {
            "symptoms": ["fatigue"],
            "clinical_summary": "User reports fatigue.",
            "confidence_level": 0.9
        },
        "agent_decisioning": {},
        "ehr_interoperability": {},
        "output_metadata": {}
    }

    result = agent.run(fake_structured, retrieval_context=None)

    # Core structure
    assert "report_sections" in result
    assert isinstance(result["report_sections"]["overview"], str)

    # Safety layer must exist
    assert "safety_checks" in result
    assert result["safety_checks"]["guard_passed"] is True
    assert isinstance(result["safety_checks"]["events"], list)

    overview_text = result["report_sections"]["overview"].lower()

    # Ensure no direct diagnostic language
    forbidden_phrases = [
        "you have",
        "diagnosed",
        "suffering from",
        "confirmed",
        "prescribed",
        "take 10mg",
    ]
    assert not any(p in overview_text for p in forbidden_phrases)


def test_output_agent_with_retrieval_context(patch_openai):
    agent = OutputAgent(model="gpt-4o-mini")

    fake_structured = {"trace": {"input_id": "test2"}}

    retrieval_context = [
        {
            "text": "Fatigue may relate to sleep quality.",
            "source": "kb_doc_1",
            "score": 0.87,
        }
    ]

    result = agent.run(fake_structured, retrieval_context=retrieval_context)

    assert "report_sections" in result
    assert "safety_checks" in result
    assert result["safety_checks"]["guard_passed"] is True

