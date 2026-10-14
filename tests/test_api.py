import pytest
from fastapi.testclient import TestClient

from chatbot_api.config import Settings
from chatbot_api.dependencies import get_chat_service
from chatbot_api.main import app, create_app
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
        live_response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert isinstance(response.json()["llm_configured"], bool)
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}
    assert live_response.headers["X-Request-ID"]
    assert live_response.headers["Cache-Control"] == "no-store"


def test_readiness_reflects_provider_configuration() -> None:
    ready_app = create_app(Settings(_env_file=None, gemini_api_key="test-key"))
    not_ready_app = create_app(Settings(_env_file=None, gemini_api_key=None))

    with TestClient(ready_app) as client:
        ready_response = client.get("/health/ready")
    with TestClient(not_ready_app) as client:
        not_ready_response = client.get("/health/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready", "llm_configured": True}
    assert not_ready_response.status_code == 503
    assert not_ready_response.json() == {
        "status": "not_ready",
        "llm_configured": False,
    }


def test_production_startup_requires_gemini_key() -> None:
    production_settings = Settings(
        _env_file=None,
        app_environment="production",
        app_docs_enabled=False,
        gemini_api_key=None,
    )
    production_app = create_app(production_settings)

    with (
        pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"),
        TestClient(production_app),
    ):
        pass


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
            retry_after_seconds=30,
        )


def test_chat_returns_safe_provider_errors() -> None:
    app.dependency_overrides[get_chat_service] = FailingChatService

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/chat", json={"message": "Hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json() == {
        "detail": {
            "code": "provider_rate_limited",
            "message": "The provider is busy.",
        }
    }
