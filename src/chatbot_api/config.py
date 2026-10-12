from functools import lru_cache

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
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_max_output_tokens: int = Field(default=1024, ge=16, le=128_000)
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    chatbot_system_prompt: str = "You are a helpful, concise assistant."

    @property
    def has_openai_api_key(self) -> bool:
        if self.openai_api_key is None:
            return False
        value = self.openai_api_key.get_secret_value().strip()
        return bool(value and value != "your_api_key_here")


@lru_cache
def get_settings() -> Settings:
    return Settings()
