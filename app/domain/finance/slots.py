from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator

SLOT_KEYS = [
    "intent",
    "amount",
    "currency",
    "target_date",
]

REQUIRED_SLOTS = [
    "intent",
    "amount",
    "currency",
]

DEFAULT_SLOT_VALUES = {
    "intent": None,
    "amount": None,
    "currency": "VND",
    "target_date": None,
}

SLOT_QUESTION = {
    "intent": "Bạn muốn theo dõi chi tiêu, tiết kiệm hay đầu tư?",
    "amount": "Số tiền bạn muốn đặt mục tiêu là bao nhiêu?",
    "currency": "Bạn dùng loại tiền tệ nào? (VND/USD)",
    "target_date": "Bạn muốn đạt mục tiêu vào thời điểm nào? (yyyy-mm-dd)",
}

class FinanceSlotData(BaseModel):
    intent: Literal["expense", "saving", "investment", ""] | None = None
    amount: float | None = None
    currency: Literal["VND", "USD"] = "VND"
    target_date: str | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("amount must be positive")
        return value

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = date.fromisoformat(value)
        return parsed.isoformat()
