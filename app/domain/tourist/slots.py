from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator

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

class TouristSlotData(BaseModel):
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
