from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict
import jsonschema
from jsonschema import ValidationError
import openai


# Paths 
ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT_DIR / "llm" / "schemas" / "structured_output.json"
PROMPT_PATH = ROOT_DIR / "llm" / "prompts" / "structuring.txt"

# Exceptions 
class StructuringError(Exception):
    pass

class LLMCallError(StructuringError):
    pass

class JSONParsingError(StructuringError):
    pass

class SchemaValidationError(StructuringError):
    pass

# Loaders 
# Load structured output JSON schema.
def load_structured_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

# Load LLM system structuring prompt.
def load_structuring_prompt() -> str:
    with PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()

# Extract the first valid JSON object from LLM output.
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
# Enterprise-grade LLM structuring engine.
class StructuringAgent:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        openai_api_key: str | None = None,
    ) -> None:
        """Initialize agent with model and API key."""
        self.model = model
        openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing.")

        openai.api_key = openai_api_key
        self._schema = load_structured_schema()
        self._base_prompt = load_structuring_prompt()
    
    # Run full structuring pipeline: LLM → JSON → Schema validation.
    def run(self, health_input: Dict[str, Any]) -> Dict[str, Any]:
        messages = self._build_messages(health_input)
        raw_output = self._call_llm(messages)
        json_str = extract_json_block(raw_output)

        try:
            structured = json.loads(json_str)
        except Exception as exc:
            raise JSONParsingError(f"JSON parse failed: {exc}") from exc

        self._validate_schema(structured)
        return structured
    # Build system + user messages for LLM call.
    def _build_messages(self, health_input: Dict[str, Any]) -> list[Dict[str, str]]:
        schema_json = json.dumps(self._schema, indent=2)
        input_json = json.dumps(health_input, indent=2)

        user_content = (
            "HealthInput:\n"
            f"{input_json}\n\n"
            "Target JSON Schema:\n"
            f"{schema_json}\n\n"
            "Return ONLY valid JSON."
        )

        return [
            {"role": "system", "content": self._base_prompt},
            {"role": "user", "content": user_content},
        ]
    # Call OpenAI Chat Completion API.
    def _call_llm(self, messages: list[Dict[str, str]]) -> str:
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
            )
        except Exception as exc:
            raise LLMCallError(f"LLM call failed: {exc}") from exc

        try:
            content = response["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMCallError(f"Malformed LLM response: {exc}") from exc

        if not content:
            raise LLMCallError("LLM returned empty response.")

        return content
    # Validate structured output against JSON schema.
    def _validate_schema(self, structured: Dict[str, Any]) -> None:
        try:
            jsonschema.validate(instance=structured, schema=self._schema)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Schema validation error: {exc.message}"
            ) from exc

