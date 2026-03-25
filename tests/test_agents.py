import json
import pytest
from agents.output_agent import OutputAgent


# Synthetic OpenAI Mock: Simulates OpenAI ChatCompletion API response.
# Returns deterministic JSON to ensure: CI stability, no external API dependency, and fully reproducible tests
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
# Mock replacement for OpenAI client. Ensures OutputAgent does not call real API.
    def __init__(self, *args, **kwargs):
        self.chat = SyntheticChat()


# Pytest Fixture
@pytest.fixture
# Replace OpenAI client with deterministic mock.
def patch_openai(monkeypatch):
    monkeypatch.setattr("agents.output_agent.OpenAI", SyntheticOpenAI)


# Test 1: Minimal Structured Input: Validate OutputAgent with minimal structured input.
# Ensures schema compatibility is with StructuredHealthOutput, report structure is generated, and safety guard is enforced.
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

    # Report Structure 
    assert "report_sections" in result
    assert isinstance(result["report_sections"]["overview"], str)

    # Safety Layer
    assert "safety_checks" in result
    assert result["safety_checks"]["guard_passed"] is True
    assert isinstance(result["safety_checks"]["events"], list)

    # Safety Content Check 
    overview_text = result["report_sections"]["overview"].lower()

    # Ensure no direct diagnosis or unsafe medical claims
    forbidden_phrases = [
        "you have",
        "diagnosed",
        "suffering from",
        "confirmed",
        "prescribed",
        "take 10mg",
    ]

    assert not any(p in overview_text for p in forbidden_phrases)


# Test 2: With Retrieval Context (RAG): Validate OutputAgent with RAG context. 
# Ensures retrieval context does not break output schema and safety layer is still enforced.
def test_output_agent_with_retrieval_context(patch_openai):

    agent = OutputAgent(model="gpt-4o-mini")

    # Minimal valid structured input
    fake_structured = {
        "trace": {"input_id": "test2"},
        "compliance": {"consent_granted": True},
        "clinical_structuring": {},
        "agent_decisioning": {},
        "ehr_interoperability": {},
        "output_metadata": {}
    }

    retrieval_context = [
        {
            "text": "Fatigue may relate to sleep quality.",
            "source": "kb_doc_1",
            "score": 0.87,
        }
    ]

    result = agent.run(fake_structured, retrieval_context=retrieval_context)

    # Core Output 
    assert "report_sections" in result

    # Safety Layer 
    assert "safety_checks" in result
    assert result["safety_checks"]["guard_passed"] is True

# Structured Output Schema Test 
def test_structured_output_schema_basic():

    from agents.structuring_agent import StructuringAgent

    agent = StructuringAgent(mode="mock")

    fake_input = {
        "input_id": "test_schema",
        "user_id": "user_x",
        "raw_text": "I have a headache",
        "source": "web",
        "input_type": "chat",
        "timestamp": "2025-01-01T00:00:00Z",
        "contains_phi": False,
        "consent_granted": True,
    }

    result = agent.run(fake_input)

    # Top-level fields (Issue 13 A)
    assert "trace" in result
    assert "compliance" in result
    assert "clinical_structuring" in result
    assert "agent_decisioning" in result
    assert "ehr_interoperability" in result
    assert "output_metadata" in result

    # Nested required fields (partial sanity check)
    clinical = result["clinical_structuring"]
    assert "symptoms" in clinical
    assert "clinical_summary" in clinical
    assert "confidence_level" in clinical