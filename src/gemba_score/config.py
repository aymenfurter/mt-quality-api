"""Application configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment / .env."""

    app_name: str = Field(default="GEMBA-Score API", description="Human readable service name")
    app_env: str = Field(default="development", description="Environment label (dev/stage/prod)")
    api_v1_prefix: str = Field(default="/api/v1", description="API prefix")
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="sqlite+aiosqlite:///./.data/dev.db", alias="DATABASE_URL")

    # Azure OpenAI configuration
    azure_openai_endpoint: AnyUrl = Field(description="Azure OpenAI endpoint base URL")
    azure_openai_api_key: str = Field(description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(default="2024-08-01-preview")
    azure_openai_deployment: str = Field(description="Azure OpenAI deployment (model) name")
    default_llm_model: str = Field(
        default="gpt-4o-mini",
        description="Default model identifier to persist",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()  # type: ignore[arg-type]


__all__ = ["Settings", "get_settings"]
