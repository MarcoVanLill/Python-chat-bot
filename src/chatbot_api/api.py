from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from chatbot_api.dependencies import get_chat_service
from chatbot_api.schemas import ChatRequest, ChatResponse
from chatbot_api.service import ChatService, ChatServiceError

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the chatbot",
)
async def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    try:
        result = await service.reply(request.message, request.previous_response_id)
    except ChatServiceError as exc:
        headers = None
        if exc.retry_after_seconds is not None:
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
            headers=headers,
        ) from exc

    return ChatResponse(
        message=result.message,
        response_id=result.response_id,
        model=result.model,
    )
