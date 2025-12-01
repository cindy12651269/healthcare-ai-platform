from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

# Centralized application configuration. All environment variables are loaded here.
class Settings(BaseSettings):
    # App
    app_env: str = Field(default="local", env="APP_ENV")
    app_name: str = Field(default="healthcare-ai-platform", env="APP_NAME")

    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")

    # OpenAI / LLM
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", env="OPENAI_MODEL")

    # PostgreSQL
    postgres_user: str = Field(..., env="POSTGRES_USER")
    postgres_password: str = Field(..., env="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., env="POSTGRES_DB")
    postgres_host: str = Field(default="db", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")

    # Redis
    redis_host: str = Field(default="redis", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
# Cached settings loader. Ensures settings are loaded once and reused across the app.
def get_settings() -> Settings:
    return Settings()
