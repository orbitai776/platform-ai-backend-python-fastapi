from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from typing import Any

from unidecode import unidecode

from app.domain.booking.slots import DEFAULT_SLOT_VALUES, SLOT_KEYS

LOW_CONFIDENCE_THRESHOLD = 0.62
HEURISTIC_FASTPATH_THRESHOLD = 0.84

_SEATING_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("private_room", ("phong rieng", "private room", "vip")),
    ("outdoor", ("ngoai troi", "san vuon", "ban ngoai", "outdoor")),
    ("indoor", ("trong nha", "trong phong", "indoor")),
)


def normalize_text(text: str) -> str:
    lowered = unidecode(text.lower().strip())
    lowered = re.sub(r"[^a-z0-9/:,\-\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def build_llm_cache_key(message: str, current_slots: dict[str, Any]) -> str:
    payload = f"{message.strip()}|{json.dumps(current_slots, ensure_ascii=False, sort_keys=True, default=str)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_missing_slot_value(key: str, value: Any) -> bool:
    if value is None:
        return True

    default_value = DEFAULT_SLOT_VALUES.get(key)
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(default_value, str) and isinstance(value, str) and default_value.lower() == value.lower():
        return True
    if isinstance(default_value, (int, float)) and isinstance(value, (int, float)) and value == default_value:
        return True
    return False


def _compute_overall_confidence(slots: dict[str, Any], scores: dict[str, float]) -> float:
    values = [scores[k] for k in SLOT_KEYS if k in scores and not _is_missing_slot_value(k, slots.get(k))]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _extract_party_size(text: str) -> int | None:
    patterns = (
        r"(\d{1,2})\s*(nguoi|khach|person|people|ban)",
        r"ban\s*(\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = int(match.group(1))
        if value > 0:
            return value
    return None


def _extract_booking_time(text: str) -> str | None:
    patterns = (
        r"(?:luc|vao luc|gio|khoang)\s*(\d{1,2})(?::|h)?(\d{2})?",
        r"\b(\d{1,2})h(\d{2})?\b",
        r"\b(\d{1,2}):(\d{2})\b",
    )

    match = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            break
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "00")

    if hour > 23 or minute > 59:
        return None

    if hour <= 11 and any(token in text for token in ("chieu", "toi", "pm")):
        hour += 12
    return f"{hour:02d}:{minute:02d}"


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
        current_year = date.today().year
        year = current_year
    else:
        year = int(year_text)
        if year < 100:
            year += 2000

    try:
        parsed = date(year, month, day)
        return parsed.isoformat()
    except ValueError:
        return None


def _extract_area(text: str) -> str | None:
    cues = (
        "o ",
        "tai ",
        "khu vuc ",
        "quan ",
        "gan ",
    )
    for cue in cues:
        idx = text.find(cue)
        if idx < 0:
            continue
        raw = text[idx + len(cue):]
        raw = re.split(r"[,.]| luc | vao ngay | ngay | cho | vao luc | gio ", raw)[0].strip()
        if len(raw) >= 2:
            return raw
    return None


def _extract_restaurant_name(message: str) -> str | None:
    original = message.strip()
    patterns = (
        r"nha hang\s+([^,\.]+)",
        r"quan an\s+([^,\.]+)",
        r"restaurant\s+([^,\.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, unidecode(original.lower()))
        if not match:
            continue
        value = original[match.start(1):match.end(1)].strip(" -")
        if value:
            return value
    return None


def _extract_seating_preference(text: str) -> str | None:
    for preference, keywords in _SEATING_PATTERNS:
        if any(keyword in text for keyword in keywords):
            return preference
    return None


def heuristic_extract_with_meta(message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    text = normalize_text(message)

    result: dict[str, Any] = dict(DEFAULT_SLOT_VALUES)
    confidence: dict[str, float] = {}

    restaurant_name = _extract_restaurant_name(message)
    if restaurant_name:
        result["restaurant_name"] = restaurant_name
        confidence["restaurant_name"] = 0.86

    area = _extract_area(text)
    if area:
        result["area"] = area
        confidence["area"] = 0.82

    booking_date = _extract_booking_date(text)
    if booking_date:
        result["booking_date"] = booking_date
        confidence["booking_date"] = 0.9

    booking_time = _extract_booking_time(text)
    if booking_time:
        result["booking_time"] = booking_time
        confidence["booking_time"] = 0.88

    party_size = _extract_party_size(text)
    if party_size is not None:
        result["party_size"] = party_size
        confidence["party_size"] = 0.9

    seating = _extract_seating_preference(text)
    if seating:
        result["seating_preference"] = seating
        confidence["seating_preference"] = 0.8

    overall_confidence = _compute_overall_confidence(result, confidence)
    elapsed_ms = (time.perf_counter() - started) * 1000
    metadata = {
        "overall_confidence": round(overall_confidence, 4),
        "confidence_by_slot": confidence,
        "normalized_message": text,
        "latency_ms": round(elapsed_ms, 3),
    }
    return result, metadata