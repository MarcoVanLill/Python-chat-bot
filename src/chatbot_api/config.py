from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Python Chatbot API"
    app_version: str = "0.1.0"
    app_environment: Literal["development", "test", "production"] = "development"
    app_docs_enabled: bool = True
    cors_allowed_origins: list[str] = []
    trusted_hosts: list[str] = []
    chatbot_request_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    chatbot_max_concurrent_requests: int = Field(default=20, ge=1, le=1_000)
    chatbot_retry_after_seconds: int = Field(default=30, ge=1, le=3_600)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_max_output_tokens: int = Field(default=4_096, ge=16, le=65_536)
    gemini_timeout_seconds: float = Field(default=20.0, gt=0, le=300)
    gemini_retry_attempts: int = Field(default=2, ge=1, le=5)
    gemini_thinking_level: Literal["low", "medium", "high"] = "low"
    gemini_enable_google_search: bool = False
    chatbot_system_prompt: str = "You are a helpful, concise assistant."

    @property
    def has_gemini_api_key(self) -> bool:
        if self.gemini_api_key is None:
            return False
        value = self.gemini_api_key.get_secret_value().strip()
        return bool(value and value != "your_api_key_here")


@lru_cache
def get_settings() -> Settings:
    return Settings()
