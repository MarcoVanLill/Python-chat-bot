from functools import lru_cache

from fastapi import HTTPException, status

from chatbot_api.config import get_settings
from chatbot_api.service import ChatService, GeminiChatService


@lru_cache
def get_chat_service() -> ChatService:
    settings = get_settings()
    if not settings.has_gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_not_configured",
                "message": "Set GEMINI_API_KEY before using the chat endpoint.",
            },
        )

    assert settings.gemini_api_key is not None
    return GeminiChatService(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        instructions=settings.chatbot_system_prompt,
        max_output_tokens=settings.gemini_max_output_tokens,
        timeout_seconds=settings.gemini_timeout_seconds,
        retry_attempts=settings.gemini_retry_attempts,
        request_timeout_seconds=settings.chatbot_request_timeout_seconds,
        max_concurrent_requests=settings.chatbot_max_concurrent_requests,
        retry_after_seconds=settings.chatbot_retry_after_seconds,
        thinking_level=settings.gemini_thinking_level,
        enable_google_search=settings.gemini_enable_google_search,
    )
