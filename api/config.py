from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # App Info
    app_name: str = "Healthcare AI Platform"
    app_env: str = Field(default="local", description="local | test | prod")
    pipeline_version: str = "v0.1.0"

    # LLM Config 
    # LLM_MODE=mock (default, deterministic, no key) | real (OpenAI). Anything else fails at startup.
    llm_provider: str = "openai"
    llm_mode: str = Field(default="mock", description="mock | real")
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # Database Config
    # Default targets a host-run API with the Compose `db` port published on localhost.
    # docker-compose.yml overrides DATABASE_URL for the api container (host `db`).
    database_url: str = Field(
        default="postgresql+psycopg2://healthcare_ai:healthcare_ai@localhost:5432/healthcare_ai"
    )
    db_echo: bool = False

    # Feature Flags
    enable_rag: bool = True
    enable_safety_guard: bool = True
    enable_persistence: bool = True

    # CORS: comma-separated browser origins allowed to call the API (local Next.js UI by default)
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("llm_mode", mode="before")
    @classmethod
    def _check_llm_mode(cls, value):
        from llm.provider import validate_llm_mode

        try:
            return validate_llm_mode(value)
        except Exception as exc:
            raise ValueError(str(exc)) from None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra="ignore"

@lru_cache
# Cached settings instance to avoid re-reading environment variables multiple times.
# Safe to import anywhere (API, pipeline, DB).
def get_settings() -> Settings:
    return Settings()
