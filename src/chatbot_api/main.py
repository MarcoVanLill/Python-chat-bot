import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from chatbot_api.api import router as chat_router
from chatbot_api.config import Settings, get_settings
from chatbot_api.dependencies import get_chat_service
from chatbot_api.schemas import (
    ApiInfoResponse,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)

logger = logging.getLogger(__name__)
request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    settings = app_settings or get_settings()
    docs_url = "/docs" if settings.app_docs_enabled else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.app_environment == "production" and not settings.has_gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required in production.")

        try:
            yield
        finally:
            if get_chat_service.cache_info().currsize:
                service = get_chat_service()
                close = getattr(service, "close", None)
                if close is not None:
                    await close()
            get_chat_service.cache_clear()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A small chatbot API backed by the Gemini Interactions API.",
        docs_url=docs_url,
        redoc_url="/redoc" if settings.app_docs_enabled else None,
        openapi_url="/openapi.json" if settings.app_docs_enabled else None,
        lifespan=lifespan,
    )

    if settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if request_id_pattern.fullmatch(supplied_request_id)
            else uuid4().hex
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid4().hex)
        logger.exception("Unhandled request error request_id=%s", request_id, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )

    app.include_router(chat_router)

    @app.get("/", response_model=ApiInfoResponse, tags=["system"])
    async def api_info() -> ApiInfoResponse:
        return ApiInfoResponse(
            name=settings.app_name,
            version=settings.app_version,
            docs_url=docs_url,
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(llm_configured=settings.has_gemini_api_key)

    @app.get("/health/live", response_model=LivenessResponse, tags=["system"])
    async def liveness() -> LivenessResponse:
        return LivenessResponse()

    @app.get(
        "/health/ready",
        response_model=ReadinessResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
        tags=["system"],
    )
    async def readiness(response: Response) -> ReadinessResponse:
        is_ready = settings.has_gemini_api_key
        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            llm_configured=is_ready,
        )

    return app


app = create_app()
