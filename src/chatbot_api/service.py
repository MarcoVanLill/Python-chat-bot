import asyncio
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import errors, types
from google.genai._gaos.lib import compat_errors as interaction_errors


@dataclass(frozen=True, slots=True)
class ChatResult:
    message: str
    response_id: str
    model: str


class ChatService(Protocol):
    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult: ...


class ChatServiceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class GeminiChatService:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        max_output_tokens: int,
        timeout_seconds: float,
        retry_attempts: int,
        request_timeout_seconds: float,
        max_concurrent_requests: int,
        retry_after_seconds: int,
        thinking_level: str,
        enable_google_search: bool,
        client: object | None = None,
    ) -> None:
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=retry_attempts,
                    initial_delay=0.5,
                    max_delay=2,
                    exp_base=2,
                    jitter=0.25,
                )
            ),
        )
        self._model = model
        self._instructions = instructions
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._retry_after_seconds = retry_after_seconds
        self._thinking_level = thinking_level
        self._enable_google_search = enable_google_search

    async def reply(self, message: str, previous_response_id: str | None) -> ChatResult:
        try:
            async with asyncio.timeout(self._request_timeout_seconds):
                async with self._semaphore:
                    return await self._reply(message, previous_response_id)
        except TimeoutError as exc:
            raise ChatServiceError(
                "The language model timed out. Try again shortly.",
                code="provider_timeout",
                status_code=504,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc

    async def close(self) -> None:
        await self._client.aio.aclose()

    async def _reply(self, message: str, previous_response_id: str | None) -> ChatResult:
        request: dict[str, object] = {
            "model": self._model,
            "input": message,
            "system_instruction": self._instructions,
            "generation_config": {
                "max_output_tokens": self._max_output_tokens,
                "thinking_level": self._thinking_level,
            },
            "store": True,
        }
        if self._enable_google_search:
            request["tools"] = [{"type": "google_search"}]
        if previous_response_id is not None:
            request["previous_interaction_id"] = previous_response_id

        try:
            interaction = await self._client.aio.interactions.create(
                **request,
                timeout=self._timeout_seconds,
            )
        except interaction_errors.APITimeoutError as exc:
            raise ChatServiceError(
                "The language model timed out. Try again shortly.",
                code="provider_timeout",
                status_code=504,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except (
            interaction_errors.AuthenticationError,
            interaction_errors.PermissionDeniedError,
        ) as exc:
            raise ChatServiceError(
                "The language model credentials were rejected.",
                code="provider_authentication_failed",
                status_code=503,
            ) from exc
        except interaction_errors.RateLimitError as exc:
            raise ChatServiceError(
                "The language model quota was exceeded. Try again later or disable Google Search.",
                code="provider_rate_limited",
                status_code=429,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except (
            interaction_errors.BadRequestError,
            interaction_errors.NotFoundError,
            interaction_errors.UnprocessableEntityError,
        ) as exc:
            raise ChatServiceError(
                "The request or previous_response_id was rejected.",
                code="invalid_conversation",
                status_code=400,
            ) from exc
        except interaction_errors.APIConnectionError as exc:
            raise ChatServiceError(
                "The language model could not be reached.",
                code="provider_unavailable",
                status_code=503,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except interaction_errors.InternalServerError as exc:
            raise ChatServiceError(
                "The language model is temporarily unavailable.",
                code="provider_unavailable",
                status_code=503,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except interaction_errors.APIStatusError as exc:
            raise ChatServiceError(
                "The language model returned an unexpected error.",
                code="provider_error",
                status_code=502,
            ) from exc
        except errors.ClientError as exc:
            if exc.code in {401, 403}:
                raise ChatServiceError(
                    "The language model credentials were rejected.",
                    code="provider_authentication_failed",
                    status_code=503,
                ) from exc
            if exc.code == 429:
                raise ChatServiceError(
                    "The language model is temporarily rate limited. Try again shortly.",
                    code="provider_rate_limited",
                    status_code=429,
                    retry_after_seconds=self._retry_after_seconds,
                ) from exc
            if exc.code in {400, 404}:
                raise ChatServiceError(
                    "The request or previous_response_id was rejected.",
                    code="invalid_conversation",
                    status_code=400,
                ) from exc
            raise ChatServiceError(
                "The language model rejected the request.",
                code="provider_error",
                status_code=502,
            ) from exc
        except errors.ServerError as exc:
            raise ChatServiceError(
                "The language model is temporarily unavailable.",
                code="provider_unavailable",
                status_code=503,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except errors.APIError as exc:
            raise ChatServiceError(
                "The language model could not be reached.",
                code="provider_unavailable",
                status_code=503,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc
        except interaction_errors.APIError as exc:
            raise ChatServiceError(
                "The language model could not be reached.",
                code="provider_unavailable",
                status_code=503,
                retry_after_seconds=self._retry_after_seconds,
            ) from exc

        output_text = (interaction.output_text or "").strip()
        if not output_text:
            raise ChatServiceError(
                "The language model returned no text.",
                code="empty_provider_response",
                status_code=502,
            )

        return ChatResult(
            message=output_text,
            response_id=interaction.id,
            model=self._model,
        )
