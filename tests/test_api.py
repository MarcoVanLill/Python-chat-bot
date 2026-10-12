from fastapi.testclient import TestClient

from chatbot_api.dependencies import get_chat_service
from chatbot_api.main import app
from chatbot_api.service import ChatResult, ChatServiceError


class FakeChatService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult:
        self.calls.append((message, previous_response_id))
        return ChatResult(
            message="Hello from the fake assistant.",
            response_id="resp_test_123",
            model="test-model",
        )


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert isinstance(response.json()["llm_configured"], bool)


def test_chat_returns_provider_result_and_forwards_conversation_id() -> None:
    fake_service = FakeChatService()
    app.dependency_overrides[get_chat_service] = lambda: fake_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                json={
                    "message": "  Hello  ",
                    "previous_response_id": "resp_previous",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello from the fake assistant.",
        "response_id": "resp_test_123",
        "model": "test-model",
    }
    assert fake_service.calls == [("Hello", "resp_previous")]


def test_chat_rejects_blank_messages() -> None:
    app.dependency_overrides[get_chat_service] = FakeChatService

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/chat", json={"message": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_chat_rejects_unknown_fields() -> None:
    app.dependency_overrides[get_chat_service] = FakeChatService

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                json={"message": "Hello", "unexpected": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


class FailingChatService:
    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult:
        raise ChatServiceError(
            "The provider is busy.",
            code="provider_rate_limited",
            status_code=429,
        )


def test_chat_returns_safe_provider_errors() -> None:
    app.dependency_overrides[get_chat_service] = FailingChatService

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/chat", json={"message": "Hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": "provider_rate_limited",
            "message": "The provider is busy.",
        }
    }
