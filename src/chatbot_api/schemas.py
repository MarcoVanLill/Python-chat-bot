from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MessageText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]
ResponseId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: MessageText = Field(
        description="The user's next message.",
        examples=["Explain dependency injection in one paragraph."],
    )
    previous_response_id: ResponseId | None = Field(
        default=None,
        description="The response_id returned by the previous turn, for multi-turn chat.",
        examples=["resp_abc123"],
    )


class ChatResponse(BaseModel):
    message: str
    response_id: str
    model: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    llm_configured: bool


class ApiInfoResponse(BaseModel):
    name: str
    version: str
    docs_url: str
