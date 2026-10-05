# OpenAI provider wrapper (real mode only). Server-side: the key comes from settings, never from a request.
# Explicit timeout, small bounded retry for transient failures, sanitized errors, JSON-object output only.
from __future__ import annotations
import copy
import json
import logging
import re
import time
from typing import Any, Callable, Dict, Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from llm.provider import (
    LLMConfigurationError,
    LLMMalformedOutputError,
    LLMProviderError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

# Retried: timeouts, connection errors, 429 and 5xx. Not retried: other 4xx (auth, bad request), malformed output.
TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)


# Keywords OpenAI strict structured outputs reject; the caller's own jsonschema validation still enforces them.
_UNSUPPORTED_KEYWORDS = ("$schema", "minLength", "maxLength")


# Convert a project JSON Schema into an OpenAI strict-mode schema:
# every object lists all its properties as required and disallows extras; properties that were optional
# become nullable (strict mode has no optional keys), and `strip_optional_nulls` removes those nulls again.
def to_strict_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    node = {k: copy.deepcopy(v) for k, v in schema.items() if k not in _UNSUPPORTED_KEYWORDS}

    if node.get("type") == "object":
        props = {name: to_strict_schema(sub) for name, sub in node.get("properties", {}).items()}
        for name in set(props) - set(node.get("required", [])):
            props[name] = _nullable(props[name])
        node["properties"] = props
        node["required"] = list(props)
        node["additionalProperties"] = False

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        node["items"] = to_strict_schema(node["items"])

    return node


def _nullable(node: Dict[str, Any]) -> Dict[str, Any]:
    if node.get("type") in ("object", "array"):
        # Same shape the OpenAI SDK emits for Optional[Model] / Optional[list]
        return {"anyOf": [node, {"type": "null"}]}
    node = dict(node)
    types = node.get("type")
    if isinstance(types, str):
        node["type"] = [types, "null"]
    if "enum" in node and None not in node["enum"]:
        node["enum"] = [*node["enum"], None]
    return node


# Drop null values for keys the original schema marks optional (the strict-mode encoding of "absent").
# Nulls in required fields are left in place so schema validation rejects them.
def strip_optional_nulls(data: Any, schema: Dict[str, Any]) -> Any:
    if isinstance(data, dict) and schema.get("type") == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        return {
            key: strip_optional_nulls(value, props.get(key, {}))
            for key, value in data.items()
            if not (value is None and key in props and key not in required)
        }
    if isinstance(data, list) and isinstance(schema.get("items"), dict):
        return [strip_optional_nulls(item, schema["items"]) for item in data]
    return data


def _response_format(schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if schema is None:
        return {"type": "json_object"}
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", schema.get("title") or "response")[:64]
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "schema": to_strict_schema(schema), "strict": True},
    }


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not (api_key or "").strip():
            raise LLMConfigurationError("LLM_MODE=real requires OPENAI_API_KEY to be set")
        self.model = model
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self._sleep = sleep
        # SDK-level retries are disabled so the retry policy below is the only one
        self._client = client or OpenAI(api_key=api_key, timeout=timeout, max_retries=0)

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response_format = _response_format(schema)
        last_error: LLMProviderError = LLMProviderError("LLM provider request failed")

        for attempt in range(self.max_retries + 1):
            if attempt:
                self._sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    response_format=response_format,
                    timeout=self.timeout,
                )
                break
            except APITimeoutError:
                last_error = LLMTimeoutError(f"LLM provider timed out after {self.timeout}s")
            except TRANSIENT_ERRORS as exc:
                status = getattr(exc, "status_code", None)
                last_error = LLMProviderError(
                    f"LLM provider transient failure ({type(exc).__name__}"
                    + (f", status {status}" if status else "") + ")"
                )
            except APIStatusError as exc:
                raise LLMProviderError(
                    f"LLM provider request rejected (status {exc.status_code})"
                ) from None
            except OpenAIError as exc:
                raise LLMProviderError(f"LLM provider error ({type(exc).__name__})") from None
            logger.warning(
                "LLM provider attempt %d/%d failed: %s", attempt + 1, self.max_retries + 1, last_error
            )
        else:
            raise last_error

        try:
            content = response.choices[0].message.content
            data = json.loads(content)
        except Exception:
            raise LLMMalformedOutputError("LLM provider returned output that is not valid JSON") from None
        if not isinstance(data, dict):
            raise LLMMalformedOutputError("LLM provider returned JSON that is not an object")
        return strip_optional_nulls(data, schema) if schema is not None else data
