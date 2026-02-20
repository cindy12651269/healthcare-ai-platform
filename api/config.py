from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # App Info
    app_name: str = "Healthcare AI Platform"
    app_env: str = Field(default="local", description="local | test | prod")
    pipeline_version: str = "v0.1.0"

    # LLM Config 
    llm_provider: str = "openai"
    llm_mode: str = Field(default="mock", description="mock | real")
    openai_api_key: str | None = None

    # Database Config
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/healthcare_ai"
    )
    db_echo: bool = False

    # Feature Flags
    enable_rag: bool = True
    enable_safety_guard: bool = True
    enable_persistence: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra="ignore"

@lru_cache
# Cached settings instance to avoid re-reading environment variables multiple times.
# Safe to import anywhere (API, pipeline, DB).
def get_settings() -> Settings:
    return Settings()
