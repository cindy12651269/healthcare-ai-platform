# Shared LLM execution interface (Issue #22).
# Both agents call `provider.generate_json(...)`; the provider is chosen once from LLM_MODE:
#   mock (default) → MockLLMProvider: deterministic, offline, no key needed
#   real           → OpenAIProvider (llm/providers/openai_client.py)
# There is no real → mock fallback: a misconfigured or failing real provider raises.
from __future__ import annotations
from typing import Any, Callable, Dict, Optional, Protocol

LLM_MODES = ("mock", "real")


# Sanitized application errors. Messages never contain credentials or raw provider payloads.
class LLMError(Exception):
    """Base class for controlled LLM failures."""


class LLMConfigurationError(LLMError, ValueError):
    """Invalid LLM_MODE or incomplete real-provider configuration."""


class LLMProviderError(LLMError):
    """The provider call failed (HTTP/status/connection error)."""


class LLMTimeoutError(LLMProviderError):
    """The provider did not answer within the configured timeout (after retries)."""


class LLMMalformedOutputError(LLMProviderError):
    """The provider answered, but not with a JSON object."""


class LLMProvider(Protocol):
    name: str

    # `schema` is the JSON Schema the output must satisfy; providers may use it to constrain generation.
    # Callers still validate the result against it (a provider is never trusted to have done so).
    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...


# Mock provider: delegates to the agent's deterministic builder; `context` is the agent's input.
class MockLLMProvider:
    name = "mock"

    def __init__(self, builder: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._builder = builder

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        context: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._builder(context)


def validate_llm_mode(mode: Optional[str]) -> str:
    value = (mode or "mock").strip().lower()
    if value not in LLM_MODES:
        raise LLMConfigurationError(
            f"Unsupported LLM_MODE {mode!r}; expected one of: {', '.join(LLM_MODES)}"
        )
    return value


# Resolve the effective mode: explicit argument wins, otherwise settings (env / .env), default mock.
def resolve_llm_mode(mode: Optional[str] = None) -> str:
    if mode is not None:
        return validate_llm_mode(mode)
    from api.config import get_settings

    return get_settings().llm_mode


# Fail fast when real mode is selected without the required provider configuration.
def check_llm_config(settings) -> None:
    validate_llm_mode(settings.llm_mode)
    if settings.llm_mode == "real" and not (settings.openai_api_key or "").strip():
        raise LLMConfigurationError("LLM_MODE=real requires OPENAI_API_KEY to be set")


def build_provider(
    mode: str,
    *,
    mock_builder: Callable[[Dict[str, Any]], Dict[str, Any]],
    model: Optional[str] = None,
) -> LLMProvider:
    if mode == "mock":
        return MockLLMProvider(mock_builder)

    from api.config import get_settings
    from llm.providers.openai_client import OpenAIProvider

    settings = get_settings()
    check_llm_config(settings)
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=model or settings.openai_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
