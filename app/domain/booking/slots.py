from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, field_validator

SLOT_KEYS = [
    "restaurant_name",
    "area",
    "booking_date",
    "booking_time",
    "party_size",
    "seating_preference",
]

REQUIRED_SLOTS = [
    "area",
    "booking_date",
    "booking_time",
    "party_size",
    "seating_preference",
]

DEFAULT_SLOT_VALUES = {
    "restaurant_name": None,
    "area": None,
    "booking_date": None,
    "booking_time": None,
    "party_size": None,
    "seating_preference": None,
}

SLOT_QUESTION = {
    "restaurant_name": "Bạn đã có nhà hàng cụ thể chưa? Nếu có, cho mình xin tên.",
    "area": "Bạn muốn đặt bàn ở khu vực nào?",
    "booking_date": "Bạn muốn đặt bàn vào ngày nào? (yyyy-mm-dd hoặc dd/mm)",
    "booking_time": "Bạn muốn đến lúc mấy giờ? (HH:MM)",
    "party_size": "Đoàn của bạn có bao nhiêu người?",
    "seating_preference": "Bạn thích ngồi trong nhà, ngoài trời hay phòng riêng?",
}


class BookingSlotData(BaseModel):
    restaurant_name: str | None = None
    area: str | None = None
    booking_date: str | None = None
    booking_time: str | None = None
    party_size: int | None = None
    seating_preference: Literal["indoor", "outdoor", "private_room"] | None = None

    @field_validator("booking_date")
    @classmethod
    def validate_booking_date(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = date.fromisoformat(value)
        return parsed.isoformat()

    @field_validator("booking_time")
    @classmethod
    def validate_booking_time(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = time.fromisoformat(value)
        return parsed.strftime("%H:%M")

    @field_validator("party_size")
    @classmethod
    def validate_party_size(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("party_size must be positive")
        return value