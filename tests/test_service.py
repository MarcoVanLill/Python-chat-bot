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
        model="gemini-3.8-flash",
        instructions="Be concise.",
        max_output_tokens=4_096,
        timeout_seconds=20,
        retry_attempts=2,
        request_timeout_seconds=45,
        max_concurrent_requests=20,
        retry_after_seconds=30,
        thinking_level="low",
        enable_google_search=True,
        client=client,
    )

    result = asyncio.run(service.reply("Hello", "interaction_previous"))

    assert result.message == "Hello from Gemini."
    assert result.response_id == "interaction_test_123"
    assert result.model == "gemini-3.8-flash"
    assert client.interactions.calls == [
        {
            "model": "gemini-3.8-flash",
            "input": "Hello",
            "system_instruction": "Be concise.",
            "tools": [{"type": "google_search"}],
            "generation_config": {
                "max_output_tokens": 4_096,
                "thinking_level": "low",
            },
            "store": True,
            "previous_interaction_id": "interaction_previous",
            "timeout": 20,
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
        model="gemini-3.8-flash",
        instructions="Be concise.",
        max_output_tokens=1024,
        timeout_seconds=20,
        retry_attempts=2,
        request_timeout_seconds=45,
        max_concurrent_requests=20,
        retry_after_seconds=30,
        thinking_level="low",
        enable_google_search=False,
        client=FakeGeminiClient(RateLimitedInteractions()),
    )

    with pytest.raises(ChatServiceError) as caught:
        asyncio.run(service.reply("Hello", None))

    assert caught.value.status_code == 429
    assert caught.value.code == "provider_rate_limited"
    assert caught.value.retry_after_seconds == 30


class SlowInteractions:
    async def create(self, **request: object) -> SimpleNamespace:
        await asyncio.sleep(0.1)
        return SimpleNamespace(output_text="Too late", id="interaction_late")


def test_gemini_request_has_hard_total_timeout() -> None:
    service = GeminiChatService(
        api_key="unused-test-key",
        model="gemini-3.8-flash",
        instructions="Be concise.",
        max_output_tokens=1024,
        timeout_seconds=20,
        retry_attempts=2,
        request_timeout_seconds=0.01,
        max_concurrent_requests=1,
        retry_after_seconds=15,
        thinking_level="low",
        enable_google_search=False,
        client=FakeGeminiClient(SlowInteractions()),
    )

    with pytest.raises(ChatServiceError) as caught:
        asyncio.run(service.reply("Hello", None))

    assert caught.value.status_code == 504
    assert caught.value.code == "provider_timeout"
    assert caught.value.retry_after_seconds == 15


class ConcurrencyTrackingInteractions:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def create(self, **request: object) -> SimpleNamespace:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return SimpleNamespace(output_text="OK", id="interaction_concurrency")


def test_gemini_requests_respect_concurrency_limit() -> None:
    interactions = ConcurrencyTrackingInteractions()
    service = GeminiChatService(
        api_key="unused-test-key",
        model="gemini-3.8-flash",
        instructions="Be concise.",
        max_output_tokens=1024,
        timeout_seconds=20,
        retry_attempts=2,
        request_timeout_seconds=1,
        max_concurrent_requests=1,
        retry_after_seconds=30,
        thinking_level="low",
        enable_google_search=False,
        client=FakeGeminiClient(interactions),
    )

    async def run_requests() -> None:
        await asyncio.gather(
            service.reply("First", None),
            service.reply("Second", None),
        )

    asyncio.run(run_requests())

    assert interactions.max_active == 1
