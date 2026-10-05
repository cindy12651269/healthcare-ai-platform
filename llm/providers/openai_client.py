# OpenAI provider wrapper (real mode only). Server-side: the key comes from settings, never from a request.
# Explicit timeout, small bounded retry for transient failures, sanitized errors, JSON-object output only.
from __future__ import annotations
import json
import logging
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

    def generate_json(self, *, system: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
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
                    response_format={"type": "json_object"},
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
        return data
