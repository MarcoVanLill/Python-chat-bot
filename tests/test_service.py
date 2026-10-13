import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google.genai._gaos.lib import compat_errors as interaction_errors

from chatbot_api.service import ChatServiceError, GeminiChatService


class FakeInteractions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **request: object) -> SimpleNamespace:
        self.calls.append(request)
        return SimpleNamespace(
            output_text="Hello from Gemini.",
            id="interaction_test_123",
        )


class FakeGeminiClient:
    def __init__(self, interactions: object | None = None) -> None:
        self.interactions = interactions or FakeInteractions()
        self.aio = SimpleNamespace(interactions=self.interactions)


def test_gemini_request_uses_search_config_and_conversation_id() -> None:
    client = FakeGeminiClient()
    service = GeminiChatService(
        api_key="unused-test-key",
        model="gemini-3-flash-preview",
        instructions="Be concise.",
        max_output_tokens=65_536,
        timeout_seconds=30,
        temperature=1,
        top_p=0.95,
        thinking_level="high",
        enable_google_search=True,
        client=client,
    )

    result = asyncio.run(service.reply("Hello", "interaction_previous"))

    assert result.message == "Hello from Gemini."
    assert result.response_id == "interaction_test_123"
    assert result.model == "gemini-3-flash-preview"
    assert client.interactions.calls == [
        {
            "model": "gemini-3-flash-preview",
            "input": "Hello",
            "system_instruction": "Be concise.",
            "tools": [{"type": "google_search"}],
            "generation_config": {
                "temperature": 1,
                "max_output_tokens": 65_536,
                "top_p": 0.95,
                "thinking_level": "high",
            },
            "store": True,
            "previous_interaction_id": "interaction_previous",
            "timeout": 30,
        }
    ]


class RateLimitedInteractions:
    async def create(self, **request: object) -> None:
        http_request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
        response = httpx.Response(429, request=http_request)
        raise interaction_errors.RateLimitError(
            "Quota exceeded",
            response=response,
            body={"error": {"code": "too_many_requests"}},
        )


def test_gemini_rate_limit_becomes_safe_chat_error() -> None:
    service = GeminiChatService(
        api_key="unused-test-key",
        model="gemini-3-flash-preview",
        instructions="Be concise.",
        max_output_tokens=1024,
        timeout_seconds=30,
        temperature=1,
        top_p=0.95,
        thinking_level="high",
        enable_google_search=False,
        client=FakeGeminiClient(RateLimitedInteractions()),
    )

    with pytest.raises(ChatServiceError) as caught:
        asyncio.run(service.reply("Hello", None))

    assert caught.value.status_code == 429
    assert caught.value.code == "provider_rate_limited"
