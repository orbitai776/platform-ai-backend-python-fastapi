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


def build_booking_summary_text(slots: dict[str, Any]) -> str:
    restaurant_name = slots.get("restaurant_name")
    area = slots.get("area")
    booking_date = slots.get("booking_date")
    booking_time = slots.get("booking_time")
    party_size = slots.get("party_size")
    seating_preference = slots.get("seating_preference")

    restaurant_text = restaurant_name.strip() if isinstance(restaurant_name, str) and restaurant_name.strip() else "nhà hàng phù hợp"
    area_text = area.strip() if isinstance(area, str) and area.strip() else "khu vực bạn yêu cầu"
    date_text = _format_date_vi(booking_date if isinstance(booking_date, str) else None) or "ngày bạn chọn"
    time_text = _format_time_hhmm(booking_time if isinstance(booking_time, str) else None) or "giờ bạn chọn"
    party_text = str(party_size) if isinstance(party_size, int) and party_size > 0 else "số khách đã cung cấp"

    seating_label = {
        "indoor": "trong nhà",
        "outdoor": "ngoài trời",
        "private_room": "phòng riêng",
    }.get(str(seating_preference), "trong nhà")

    return (
        f"Bạn đã yêu cầu đặt bàn tại {restaurant_text} ở {area_text} vào lúc {time_text}, {date_text} cho "
        f"{party_text} người. Ưu tiên chỗ ngồi: {seating_label}."
    )