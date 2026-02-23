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

# Loaders
def load_structured_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_structuring_prompt() -> str:
    with PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()

# Utilities

def extract_json_block(text: str) -> str:
    """
    Extract the first valid JSON object from text.
    Deterministic and test-safe.
    """
    text = text.strip()

    # Fast path
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
    Phase 1–2: Deterministic mock output, no external API calls, CI-safe, offline-safe
    Phase 3: Real LLM support will be enabled explicitly
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        mode: str | None = None,  # "mock" | "real"
    ) -> None:
        self.model = model
        self.mode = mode or os.getenv("LLM_MODE", "mock")

        # Load static assets (always safe)
        self._schema = load_structured_schema()
        self._base_prompt = load_structuring_prompt()

        if self.mode not in {"mock", "real"}:
            raise ValueError(f"Invalid LLM mode: {self.mode}")

        if self.mode == "real":
            # Explicitly disabled until Phase 3
            raise NotImplementedError(
                "Real LLM calls are disabled until Phase 3."
            )

    # Public API
    # Run structuring pipeline: Currently supports: mock mode only
    def run(self, health_input: Dict[str, Any]) -> Dict[str, Any]:
 
        if self.mode == "mock":
            structured = self._mock_structuring(health_input)
            self._validate_schema(structured)
            return structured

        # Safety net (should never be reached)
        raise StructuringError("Unsupported structuring mode.")

    # Mock Implementation (Phase 1–2)
    def _mock_structuring(self, health_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic mock output.

        This ensures:
        - predictable tests
        - no hallucinations
        - schema stability
        """
        return {
            "chief_complaint": health_input.get("raw_text", "")[:200],
            "symptoms": [],
            "duration": "unspecified",
            "severity": "unknown",
            "additional_context": {
                "source": health_input.get("source"),
                "input_type": health_input.get("input_type"),
            },
        }

    # Schema Validation
    def _validate_schema(self, structured: Dict[str, Any]) -> None:
        try:
            jsonschema.validate(instance=structured, schema=self._schema)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Schema validation error: {exc.message}"
            ) from exc

# Phase 3: Real LLM Support (INTENTIONALLY DISABLED)
#
# def _call_llm(self, messages: list[Dict[str, str]]) -> str:
#     import openai
#
#     response = openai.ChatCompletion.create(
#         model=self.model,
#         messages=messages,
#         temperature=0.1,
#         max_tokens=2048,
#     )
#
#     content = response["choices"][0]["message"]["content"]
#     if not content:
#         raise LLMCallError("LLM returned empty response.")
#
#     return content
