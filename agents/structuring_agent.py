from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
import jsonschema
from jsonschema import ValidationError
from llm.provider import LLMProvider, build_provider, resolve_llm_mode

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT_DIR / "llm" / "schemas" / "structured_output.json"
PROMPT_PATH = ROOT_DIR / "llm" / "prompts" / "structuring.txt"


# Exceptions
class StructuringError(Exception):
    """Base error for structuring failures."""


class JSONParsingError(StructuringError):
    """Raised when LLM output cannot be parsed as JSON."""


class SchemaValidationError(StructuringError):
    """Raised when output does not match JSON schema."""


class LLMCallError(StructuringError):
    """Reserved for real LLM failures (provider errors are raised as llm.provider.LLMProviderError)."""

# Load StructuredHealthOutput schema from disk.
def load_structured_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

# Load base prompt for structuring agent.
def load_structuring_prompt() -> str:
    with PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()

# Utilities
# Extract the first valid JSON object from text. Deterministic and test-safe.
def extract_json_block(text: str) -> str:

    text = text.strip()

    try:
        json.loads(text)
        return text
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise JSONParsingError("No valid JSON block found.")

    candidate = text[start : end + 1]

    try:
        json.loads(candidate)
        return candidate
    except Exception as exc:
        raise JSONParsingError(f"Invalid JSON block: {exc}") from exc


# Core Agent
class StructuringAgent:
    """
    Enterprise-grade structuring agent.

    - mock (default): deterministic output, CI-safe / offline-safe
    - real: OpenAI through the shared provider interface (llm/provider.py)
    Both modes go through provider.generate_json and the same schema validation.
    """

    def __init__(
        self,
        model: str | None = None,
        mode: str | None = None,
        provider: LLMProvider | None = None,
    ) -> None:

        self.mode = resolve_llm_mode(mode)

        # Load schema and prompt
        self._schema = load_structured_schema()
        self._base_prompt = load_structuring_prompt()

        self.provider = provider or build_provider(
            self.mode, mock_builder=self._mock_structuring, model=model
        )
        self.model = getattr(self.provider, "model", None) or model or "mock"

    def _build_prompt(self, health_input: Dict[str, Any]) -> str:
        return "".join([
            self._base_prompt,
            "\n\n----- StructuredHealthOutput JSON SCHEMA -----\n",
            json.dumps(self._schema),
            "\n\n----- HealthInput -----\n",
            json.dumps(health_input, default=str),
            "\n----- END INPUT -----",
        ])

    # Public API
    def run(self, health_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run structuring pipeline.

        Returns:
            StructuredHealthOutput (schema-compliant)
            + safety_violation_count (for observability)
        """
        structured = self.provider.generate_json(
            system="Return ONLY a valid JSON object matching the StructuredHealthOutput schema. No explanations.",
            prompt=self._build_prompt(health_input) if self.mode == "real" else "",
            context=health_input,
            schema=self._schema,
        )
        if self.mode == "real" and isinstance(structured.get("output_metadata"), dict):
            # Record what actually produced the output, regardless of what the model claims
            structured["output_metadata"]["model_version"] = self.model

        # Mandatory in both modes
        self._validate_schema(structured)

        return {
            **structured,
            "safety_violation_count": 0,
        }

    # Mock Implementation: Deterministic structured output.
    # Must match StructuredHealthOutput schema for Issue 13 evaluation metrics.
    def _mock_structuring(self, health_input: Dict[str, Any]) -> Dict[str, Any]:

        return {
            # Trace Layer
            "trace": {
                "input_id": health_input.get("input_id"),
                "user_id": health_input.get("user_id"),
                "timestamp": health_input.get("timestamp"),
                "source": health_input.get("source"),
                "input_type": health_input.get("input_type"),
            },

            # Compliance Layer
            "compliance": {
                "contains_phi": health_input.get("contains_phi", False),
                "consent_granted": health_input.get("consent_granted", True),
                "data_zone": "public_zone",
                "audit_required": False,
            },

            # Clinical Layer
            "clinical_structuring": {
                "chief_complaint": health_input.get("raw_text", "")[:200],
                "symptoms": [],
                "clinical_summary": "mock summary",
                "confidence_level": 0.9,
            },

            # Decision Layer
            "agent_decisioning": {},

            # Interoperability Layer
            "ehr_interoperability": {},

            # Metadata Layer
            "output_metadata": {
                "generated_at": "2025-01-01T00:00:00Z",
                "model_version": "mock",
                "prompt_version": "v1",
            },
        }

    # Schema Validation
    # Validate structured output against JSON schema.
    def _validate_schema(self, structured: Dict[str, Any]) -> None:
        try:
            jsonschema.validate(instance=structured, schema=self._schema)
        except ValidationError as exc:
            path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
            raise SchemaValidationError(
                f"Schema validation error at {path}: {exc.message}"
            ) from exc
