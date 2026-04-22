from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChatStatus(str, Enum):
    collecting = "collecting"
    completed = "completed"


class GenerateQueryRequest(BaseModel):
    query: str
    service_name: str = "tourist"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Tôi muốn đi Đà Lạt 3 ngày cho 2 người",
                "service_name": "tourist",
            }
        }
    )


class GenerateQueryData(BaseModel):
    content: dict[str, Any]
    usage: dict[str, Any] | None = None


class GenerateQueryResponse(BaseModel):
    data: GenerateQueryData | None
    error: str | None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatStartRequest(BaseModel):
    first_message: str | None = None
    service_name: str = "tourist"


class ChatTurnRequest(BaseModel):
    session_id: str
    message: str


class ChatTurnData(BaseModel):
    session_id: str
    service_name: str
    reply: str
    status: ChatStatus
    missing_slots: list[str]
    filled_slots: dict[str, Any]
    last_extracted: dict[str, Any] | None = None


class ChatTurnResponse(BaseModel):
    data: ChatTurnData | None
    error: str | None


class ChatStateData(BaseModel):
    session_id: str
    service_name: str
    status: ChatStatus
    missing_slots: list[str]
    filled_slots: dict[str, Any]
    history: list[ChatMessage]


class ChatStateResponse(BaseModel):
    data: ChatStateData | None
    error: str | None


class ChatDeleteData(BaseModel):
    session_id: str
    deleted: bool


class ChatDeleteResponse(BaseModel):
    data: ChatDeleteData | None
    error: str | None
