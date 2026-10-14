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
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3-flash-preview"
    gemini_max_output_tokens: int = Field(default=65_536, ge=16, le=65_536)
    gemini_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    gemini_temperature: float = Field(default=1.0, ge=0, le=2)
    gemini_top_p: float = Field(default=0.95, ge=0, le=1)
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "high"
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
