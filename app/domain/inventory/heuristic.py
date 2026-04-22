from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from app.domain.inventory.slots import DEFAULT_SLOT_VALUES
from unidecode import unidecode

HEURISTIC_FASTPATH_THRESHOLD = 0.85
LOW_CONFIDENCE_THRESHOLD = 0.6

_QUANTITY_PATTERN = re.compile(r"\b(\d+)\s*(sp|san pham|cai|items?)?\b", re.IGNORECASE)
_ITEM_PATTERN = re.compile(
    r"(?:mat\s*hang|hang|san\s*pham|item)\s*[:\-]?\s*([\w\s\-/]+)",
    re.IGNORECASE,
)
_WAREHOUSE_PATTERN = re.compile(r"\bkho\s*[:\-]?\s*([\w\s\-/]+)", re.IGNORECASE)


def _extract_booking_time(text: str) -> str | None:
    patterns = (
        r"(?:luc|vao luc|gio|khoang)\s*(\d{1,2})(?::|h)?(\d{2})?",
        r"\b(\d{1,2})h(\d{2})?\b",
        r"\b(\d{1,2}):(\d{2})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2) or "00")
        if hour > 23 or minute > 59:
            return None

        if hour <= 11 and any(token in text for token in ("chieu", "toi", "pm")):
            hour += 12
        return f"{hour:02d}:{minute:02d}"

    return None


def _extract_booking_date(text: str) -> str | None:
    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        try:
            parsed = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            return parsed.isoformat()
        except ValueError:
            return None

    dmy_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if not dmy_match:
        return None

    day = int(dmy_match.group(1))
    month = int(dmy_match.group(2))
    year_text = dmy_match.group(3)
    if year_text is None:
        year = date.today().year
    else:
        year = int(year_text)
        if year < 100:
            year += 2000

    try:
        parsed = date(year, month, day)
        return parsed.isoformat()
    except ValueError:
        return None


def build_llm_cache_key(message: str, current_slots: dict[str, Any]) -> str:
    payload = f"{message.strip()}|{json.dumps(current_slots, ensure_ascii=False, sort_keys=True, default=str)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    normalized = unidecode(text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def heuristic_extract_with_meta(message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = normalize_text(message)
    result = dict(DEFAULT_SLOT_VALUES)
    confidence: dict[str, float] = {}

    quantity_match = _QUANTITY_PATTERN.search(text)
    if quantity_match:
        result["quantity"] = int(quantity_match.group(1))
        confidence["quantity"] = 0.86

    item_match = _ITEM_PATTERN.search(text)
    if item_match:
        item_name = item_match.group(1).strip(" .,!?:;")
        if item_name:
            result["item_name"] = item_name
            confidence["item_name"] = 0.78

    warehouse_match = _WAREHOUSE_PATTERN.search(text)
    if warehouse_match:
        warehouse = warehouse_match.group(1).strip(" .,!?:;")
        if warehouse:
            result["warehouse"] = warehouse
            confidence["warehouse"] = 0.75

    booking_date = _extract_booking_date(text)
    if booking_date:
        result["booking_date"] = booking_date
        confidence["booking_date"] = 0.82

    booking_time = _extract_booking_time(text)
    if booking_time:
        result["booking_time"] = booking_time
        confidence["booking_time"] = 0.82

    filled_scores = list(confidence.values())
    overall = sum(filled_scores) / len(filled_scores) if filled_scores else 0.0
    return result, {
        "overall_confidence": overall,
        "slot_confidence": confidence,
        "latency_ms": 0.1,
    }
