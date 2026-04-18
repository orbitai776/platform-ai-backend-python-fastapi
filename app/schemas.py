from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MODEL_AI = "gpt-4o-mini"
MAX_TURNS = 10

SLOT_KEYS = [
    "search_type",
    "destination",
    "start_date",
    "duration_date",
    "adults",
    "children",
    "sort_by",
    "sort_type",
]

REQUIRED_SLOTS = [
    "search_type",
    "destination",
    "start_date",
    "duration_date",
    "adults",
    "children",
    "sort_by",
    "sort_type",
]

DEFAULT_SLOT_VALUES = {
    "search_type": None,
    "destination": None,
    "start_date": None,
    "duration_date": None,
    "adults": None,
    "children": None,
    "sort_by": "price",
    "sort_type": "asc",
}

SLOT_QUESTION = {
    "search_type": "Bạn đang tìm loại nào: tour hay villa?",
    "destination": "Bạn muốn đi đâu?",
    "start_date": "Bạn dự kiến khởi hành ngày nào? (dd/mm hoặc dd/mm/yyyy)",
    "duration_date": "Bạn đi bao nhiêu ngày?",
    "adults": "Đoàn có bao nhiêu người lớn?",
    "children": "Đoàn có bao nhiêu trẻ em? Nếu không có, vui lòng nhập 0.",
    "sort_by": "Bạn muốn sắp xếp theo giá hay đánh giá?",
    "sort_type": "Bạn muốn sắp xếp tăng dần hay giảm dần?",
}

SYSTEM_PROMPT = (
    "You are a strict slot extraction engine. Extract values from the user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do "
    "not invent facts."
)

SLOT_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "json_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "search_type",
                    "destination",
                    "start_date",
                    "duration_date",
                    "adults",
                    "children",
                    "sort_by",
                    "sort_type",
                ],
                "properties": {
                    "search_type": {
                        "type": ["string", "null"],
                        "enum": ["tour", "villa", ""],
                        "default": None,
                    },
                    "destination": {"type": ["string", "null"], "default": None},
                    "start_date": {"type": ["string", "null"], "format": "date", "default": None},
                    "duration_date": {"type": ["integer", "null"], "default": None},
                    "adults": {"type": ["integer", "null"], "default": None},
                    "children": {"type": ["integer", "null"], "default": None},
                    "sort_by": {
                        "type": "string",
                        "enum": ["price", "rating"],
                        "default": "price",
                    },
                    "sort_type": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "default": "asc",
                    },
                },
            },
        }
    }
}


class ChatStatus(str, Enum):
    collecting = "collecting"
    completed = "completed"


class SlotData(BaseModel):
    search_type: Literal["tour", "villa", ""] | None = None
    destination: str | None = None
    start_date: str | None = None
    duration_date: int | None = None
    adults: int | None = None
    children: int | None = None
    sort_by: Literal["price", "rating"] = "price"
    sort_type: Literal["asc", "desc"] = "asc"

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = date.fromisoformat(value)
        return parsed.isoformat()

    @field_validator("duration_date", "adults", "children")
    @classmethod
    def validate_non_negative(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("must be non-negative")
        return value


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
    status: ChatStatus
    missing_slots: list[str]
    filled_slots: dict[str, Any]
    last_extracted: dict[str, Any] | None = None


class ChatTurnResponse(BaseModel):
    data: ChatTurnData | None
    error: str | None


class ChatStateData(BaseModel):
    session_id: str
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
