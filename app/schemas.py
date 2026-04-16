from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MODEL_AI = "gpt-4o-mini"
MAX_TURNS = 10

SLOT_KEYS = [
    "destination",
    "start_date",
    "duration_days",
    "adults",
    "childs",
    "budget_min",
    "budget_max",
    "start_point",
    "sort_by",
    "sort_type",
    "tags",
]

REQUIRED_SLOTS = [
    "destination",
    "start_date",
    "duration_days",
    "adults",
    "childs",
    "budget_max",
    "start_point",
]

SLOT_QUESTION = {
    "destination": "Bạn muốn đi đâu?",
    "start_date": "Bạn dự kiến khởi hành ngày nào? (dd/mm hoặc dd/mm/yyyy)",
    "duration_days": "Bạn đi bao nhiêu ngày?",
    "adults": "Đoàn có bao nhiêu người lớn?",
    "childs": "Đoàn có bao nhiêu trẻ em? Nếu không có, vui lòng nhập 0.",
    "budget_max": "Ngân sách tối đa của bạn là bao nhiêu?",
    "start_point": "Bạn xuất phát từ đâu?",
}

SYSTEM_PROMPT = (
    "You are a strict slot extraction engine. Extract values from the user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do "
    "not invent facts."
)

SLOT_SCHEMA = {
    "format": {
        "type": "json_schema",
        "name": "travel_slot_extractor",
        "schema": {
            "type": "object",
            "properties": {
                "destination": {"type": ["string", "null"]},
                "start_date": {"type": ["string", "null"]},
                "duration_days": {"type": ["integer", "null"]},
                "adults": {"type": ["integer", "null"]},
                "childs": {"type": ["integer", "null"]},
                "budget_min": {"type": ["number", "null"]},
                "budget_max": {"type": ["number", "null"]},
                "start_point": {"type": ["string", "null"]},
                "sort_by": {"type": ["string", "null"]},
                "sort_type": {"type": ["string", "null"]},
                "tags": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "strict": True,
    }
}


class GenerateQueryRequest(BaseModel):
    query: str
    schema_payload: dict[str, Any] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)


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


class ChatTurnRequest(BaseModel):
    session_id: str
    message: str


class ChatTurnData(BaseModel):
    session_id: str
    reply: str
    status: str
    missing_slots: list[str]
    filled_slots: dict[str, Any]
    last_extracted: dict[str, Any] | None = None


class ChatTurnResponse(BaseModel):
    data: ChatTurnData | None
    error: str | None


class ChatStateData(BaseModel):
    session_id: str
    status: str
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
