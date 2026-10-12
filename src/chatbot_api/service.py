from dataclasses import dataclass
from typing import Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)


@dataclass(frozen=True, slots=True)
class ChatResult:
    message: str
    response_id: str
    model: str


class ChatService(Protocol):
    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult: ...


class ChatServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class OpenAIChatService:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._instructions = instructions
        self._max_output_tokens = max_output_tokens

    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult:
        request: dict[str, object] = {
            "model": self._model,
            "instructions": self._instructions,
            "input": message,
            "max_output_tokens": self._max_output_tokens,
            "store": True,
        }
        if previous_response_id is not None:
            request["previous_response_id"] = previous_response_id

        try:
            response = await self._client.responses.create(**request)
        except AuthenticationError as exc:
            raise ChatServiceError(
                "The language model credentials were rejected.",
                code="provider_authentication_failed",
                status_code=503,
            ) from exc
        except RateLimitError as exc:
            raise ChatServiceError(
                "The language model is temporarily rate limited. Try again shortly.",
                code="provider_rate_limited",
                status_code=429,
            ) from exc
        except APITimeoutError as exc:
            raise ChatServiceError(
                "The language model timed out. Try again shortly.",
                code="provider_timeout",
                status_code=504,
            ) from exc
        except APIConnectionError as exc:
            raise ChatServiceError(
                "The language model could not be reached.",
                code="provider_unavailable",
                status_code=503,
            ) from exc
        except APIStatusError as exc:
            status_code = 400 if exc.status_code == 400 else 502
            code = "invalid_conversation" if exc.status_code == 400 else "provider_error"
            message_text = (
                "The request or previous_response_id was rejected."
                if exc.status_code == 400
                else "The language model returned an unexpected error."
            )
            raise ChatServiceError(
                message_text,
                code=code,
                status_code=status_code,
            ) from exc

        output_text = response.output_text.strip()
        if not output_text:
            raise ChatServiceError(
                "The language model returned no text.",
                code="empty_provider_response",
                status_code=502,
            )

        return ChatResult(
            message=output_text,
            response_id=response.id,
            model=response.model,
        )
