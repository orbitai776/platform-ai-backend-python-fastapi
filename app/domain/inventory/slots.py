from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, field_validator

SLOT_KEYS = [
    "item_name",
    "quantity",
    "warehouse",
    "booking_date",
    "booking_time",
]

REQUIRED_SLOTS = [
    "item_name",
    "warehouse",
    "booking_date",
    "booking_time",
    "quantity",
]

DEFAULT_SLOT_VALUES = {
    "item_name": None,
    "quantity": None,
    "warehouse": None,
    "booking_date": None,
    "booking_time": None,
}

SLOT_QUESTION = {
    "item_name": "Bạn cho mình tên mặt hàng cần lưu kho.",
    "quantity": "Bạn cần giữ chỗ lưu kho cho số lượng bao nhiêu?",
    "warehouse": "Bạn muốn giữ chỗ ở kho nào? (ví dụ: Kho Bình Tân, Kho Hà Đông)",
    "booking_date": "Bạn muốn giữ chỗ kho vào ngày nào? (yyyy-mm-dd hoặc dd/mm)",
    "booking_time": "Bạn muốn giữ chỗ kho lúc mấy giờ? (HH:MM)",
}


class InventorySlotData(BaseModel):
    item_name: str | None = None
    quantity: int | None = None
    warehouse: str | None = None
    booking_date: str | None = None
    booking_time: str | None = None

    @field_validator("item_name", "warehouse")
    @classmethod
    def validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("quantity must be positive")
        return value

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
