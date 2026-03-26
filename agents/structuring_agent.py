from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict
import jsonschema
from jsonschema import ValidationError

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
    """Reserved for Phase 3 real LLM failures."""

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

    Phase 1–2:
    - Deterministic mock output
    - CI-safe / offline-safe
    - No external API calls

    Phase 3:
    - Real LLM integration (disabled for now)
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        mode: str | None = None,
    ) -> None:

        self.model = model
        self.mode = mode or os.getenv("LLM_MODE", "mock")

        # Load schema and prompt
        self._schema = load_structured_schema()
        self._base_prompt = load_structuring_prompt()

        if self.mode not in {"mock", "real"}:
            raise ValueError(f"Invalid LLM mode: {self.mode}")

        if self.mode == "real":
            raise NotImplementedError("Real LLM calls disabled until Phase 3")

    # Public API
    def run(self, health_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run structuring pipeline.

        Returns:
            StructuredHealthOutput (schema-compliant)
            + safety_violation_count (for observability)
        """
        if self.mode == "mock":
            structured = self._mock_structuring(health_input)
            self._validate_schema(structured)

            # Add safety metric (mock = no violations)
            return {
                **structured,
                "safety_violation_count": 0,
            }

        raise StructuringError("Unsupported structuring mode.")

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
            raise SchemaValidationError(
                f"Schema validation error: {exc.message}"
            ) from exc
