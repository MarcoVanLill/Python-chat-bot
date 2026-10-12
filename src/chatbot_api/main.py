from fastapi import FastAPI

from chatbot_api.api import router as chat_router
from chatbot_api.config import get_settings
from chatbot_api.schemas import ApiInfoResponse, HealthResponse

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A small chatbot API backed by the OpenAI Responses API.",
)
app.include_router(chat_router)


@app.get("/", response_model=ApiInfoResponse, tags=["system"])
async def api_info() -> ApiInfoResponse:
    return ApiInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(llm_configured=settings.has_openai_api_key)
