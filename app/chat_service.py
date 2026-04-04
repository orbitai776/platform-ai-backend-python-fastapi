from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.ai_service import call_extractor
from app.schemas import REQUIRED_SLOTS, SLOT_KEYS, SLOT_QUESTION, SLOT_SCHEMA


def default_slots() -> dict[str, Any]:
    return {key: None for key in SLOT_KEYS}


def merge_slots(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        if key in merged and value is not None:
            if isinstance(value, str) and not value.strip():
                continue
            merged[key] = value
    return merged


def missing_slots(slots: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_SLOTS:
        value = slots.get(key)
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(key)
            continue
    return missing


def status_from_missing(missing: list[str]) -> str:
    return "completed" if not missing else "collecting"


def next_question(missing: list[str]) -> str:
    if not missing:
        return "Thông tin đã đầy đủ."
    first_missing = missing[0]
    return SLOT_QUESTION.get(first_missing, f"Bạn vui lòng cung cấp {first_missing}.")


def _message_cache_key(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def _parse_date_to_iso(raw_value: str) -> str | None:
    date_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", raw_value)
    if not date_match:
        return None

    day = int(date_match.group(1))
    month = int(date_match.group(2))
    year = int(date_match.group(3)) if date_match.group(3) else 2026

    try:
        parsed = datetime(year=year, month=month, day=day)
    except ValueError:
        return None

    return parsed.strftime("%Y-%m-%d")


def _parse_numeric_token(number_str: str, unit_str: str | None) -> float:
    normalized = number_str.replace(",", ".")
    value = float(normalized)

    if not unit_str:
        return value

    unit = unit_str.lower()
    if unit in {"tr", "trieu", "triệu"}:
        return value * 1_000_000
    if unit in {"k", "nghin", "ngàn", "ngan", "nghìn"}:
        return value * 1_000
    return value


def heuristic_extract_slots(message: str) -> dict[str, Any]:
    text = message.lower().strip()
    result: dict[str, Any] = {key: None for key in SLOT_KEYS}

    cities = [
        "da nang",
        "đà nẵng",
        "ha noi",
        "hà nội",
        "sai gon",
        "tp hcm",
        "ho chi minh",
        "hồ chí minh",
        "nha trang",
        "phu quoc",
        "phú quốc",
        "da lat",
        "đà lạt",
        "hue",
        "huế",
        "hoi an",
        "hội an",
        "quy nhon",
        "quy nhơn",
        "vung tau",
        "vũng tàu",
    ]

    destination_pattern = re.search(
        r"(?:di|đi|den|đến|toi|tới)\s+([^\d,.;]{2,40})",
        text,
    )
    has_start_point_phrase = bool(re.search(r"(?:xuat phat tu|xuất phát từ)", text))
    if destination_pattern:
        candidate = destination_pattern.group(1).strip()
        result["destination"] = candidate
    elif not has_start_point_phrase:
        for city in cities:
            if city in text:
                result["destination"] = city
                break

    result["start_date"] = _parse_date_to_iso(text)

    adults_match = re.search(r"\b(\d{1,2})\s*(?:nguoi lon|người lớn|adult|adults)\b", text)
    if adults_match:
        result["adults"] = int(adults_match.group(1))

    childs_match = re.search(r"\b(\d{1,2})\s*(?:tre em|trẻ em|be|bé|child|children)\b", text)
    if childs_match:
        result["childs"] = int(childs_match.group(1))

    people_match = re.search(r"\b(\d{1,2})\s*(?:nguoi|người|khach|khách)\b", text)
    if people_match and result["adults"] is None:
        result["adults"] = int(people_match.group(1))
        if result["childs"] is None:
            result["childs"] = 0

    duration_match = re.search(r"\b(\d{1,2})\s*(?:ngay|ngày)\b", text)
    if duration_match:
        result["duration_days"] = int(duration_match.group(1))

    budget_match = re.search(
        r"(?:ngan sach|ngân sách|toi da|tối đa|duoi|dưới|gia|giá)\D*(\d+(?:[\.,]\d+)?)\s*(tr|trieu|triệu|k|nghin|nghìn|ngan|ngàn)?",
        text,
    )
    if budget_match:
        number_token = budget_match.group(1)
        unit_token = budget_match.group(2)
        result["budget_max"] = _parse_numeric_token(number_token, unit_token)

    start_point_match = re.search(r"(?:xuat phat tu|xuất phát từ|tu|từ)\s+(.+)", text)
    if start_point_match:
        candidate = start_point_match.group(1)
        candidate = re.split(r"\b(?:den|di|voi|gia|ngay)\b", candidate)[0].strip(" ,.;")
        if candidate:
            result["start_point"] = candidate

    if "re nhat" in text or "rẻ nhất" in text:
        result["sort_by"] = "price"
        result["sort_type"] = "asc"
    elif "mac nhat" in text or "mắc nhất" in text:
        result["sort_by"] = "price"
        result["sort_type"] = "desc"

    if "bien" in text or "biển" in text:
        result["tags"] = ["bien"]

    return result


async def extract_slot_update(message: str, current_slots: dict[str, Any]) -> dict[str, Any]:
    return await extract_slot_update_with_cache(message, current_slots, llm_cache=None)


async def extract_slot_update_with_cache(
    message: str,
    current_slots: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    cache_key = _message_cache_key(message)
    if llm_cache is not None and cache_key in llm_cache:
        return llm_cache[cache_key]

    try:
        extractor_result = await call_extractor(message, SLOT_SCHEMA)
        content = extractor_result.get("content", {})
        if isinstance(content, dict):
            if llm_cache is not None:
                llm_cache[cache_key] = content
            return content
    except Exception:
        pass

    heuristic_result = heuristic_extract_slots(message)
    if llm_cache is not None:
        llm_cache[cache_key] = heuristic_result
    return heuristic_result
