from __future__ import annotations

from datetime import date, time
from typing import Any


def _format_date_vi(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    try:
        parsed = date.fromisoformat(raw_value)
        return f"{parsed.day} tháng {parsed.month} năm {parsed.year}"
    except ValueError:
        return None


def _format_time_hhmm(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    try:
        parsed = time.fromisoformat(raw_value)
        return parsed.strftime("%H:%M")
    except ValueError:
        return None


def build_inventory_summary_text(slots: dict[str, Any]) -> str:
    item_name = str(slots.get("item_name") or "mặt hàng").strip()
    quantity = slots.get("quantity")
    warehouse = str(slots.get("warehouse") or "kho mặc định").strip()
    booking_date = slots.get("booking_date")
    booking_time = slots.get("booking_time")

    date_text = _format_date_vi(booking_date if isinstance(booking_date, str) else None) or "ngày bạn chọn"
    time_text = _format_time_hhmm(booking_time if isinstance(booking_time, str) else None) or "giờ bạn chọn"
    if isinstance(quantity, int) and quantity > 0:
        return (
            f"Bạn đã yêu cầu giữ chỗ lưu kho tại {warehouse} vào lúc {time_text}, {date_text} "
            f"cho {quantity} đơn vị hàng ({item_name})."
        )
    return f"Bạn đã yêu cầu giữ chỗ lưu kho tại {warehouse} vào lúc {time_text}, {date_text}."
