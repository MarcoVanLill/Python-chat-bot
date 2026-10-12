from functools import lru_cache

from fastapi import HTTPException, status

from chatbot_api.config import get_settings
from chatbot_api.service import ChatService, OpenAIChatService


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    if not settings.has_openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_not_configured",
                "message": "Set OPENAI_API_KEY before using the chat endpoint.",
            },
        )

    assert settings.openai_api_key is not None
    return OpenAIChatService(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        instructions=settings.chatbot_system_prompt,
        max_output_tokens=settings.openai_max_output_tokens,
        timeout_seconds=settings.openai_timeout_seconds,
    )
