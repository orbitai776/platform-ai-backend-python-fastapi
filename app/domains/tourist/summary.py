from __future__ import annotations

from datetime import date
from typing import Any


def _parse_date_flexible(raw_value: str) -> date | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None

    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    separators = ("/", "-")
    for sep in separators:
        if sep not in cleaned:
            continue
        parts = cleaned.split(sep)
        if len(parts) != 3:
            continue
        try:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
        except ValueError:
            continue
    return None


def _format_date_vi_long(raw_value: str | None) -> str | None:
    if not raw_value or not isinstance(raw_value, str):
        return None

    parsed = _parse_date_flexible(raw_value)
    if parsed is None:
        return None
    return f"{parsed.day} tháng {parsed.month} năm {parsed.year}"


def build_tourist_summary_text(model_filling_tourist: dict[str, Any]) -> str:
    destination = model_filling_tourist.get("destination")
    duration = model_filling_tourist.get("duration_date", model_filling_tourist.get("date"))
    start_date = model_filling_tourist.get("start_date")

    destination_text = destination.strip() if isinstance(destination, str) else "điểm đến"
    date_text = _format_date_vi_long(start_date if isinstance(start_date, str) else None)

    duration_text = None
    if isinstance(duration, int) and duration > 0:
        duration_text = f"{duration} ngày"
    elif isinstance(duration, str) and duration.strip().isdigit() and int(duration.strip()) > 0:
        duration_text = f"{int(duration.strip())} ngày"

    if duration_text and date_text:
        return f"Bạn đã lựa chọn tìm kiếm đi {destination_text} {duration_text}, bắt đầu từ {date_text}."
    if duration_text:
        return f"Bạn đã lựa chọn tìm kiếm đi {destination_text} trong {duration_text}."
    if date_text:
        return f"Bạn đã lựa chọn tìm kiếm đi {destination_text}, bắt đầu từ {date_text}."
    return f"Bạn đã lựa chọn tìm kiếm đi {destination_text}."
