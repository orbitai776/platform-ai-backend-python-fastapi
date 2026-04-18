from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from flashtext import KeywordProcessor
from unidecode import unidecode

from app.schemas import DEFAULT_SLOT_VALUES, SLOT_KEYS
from app.extractor.city import DESTINATION_CUES, best_city_match, extract_city_after_cues, extract_route_cities
from app.extractor.date import parse_date_to_iso
from app.extractor.people import extract_duration_days, extract_people_slots

LOW_CONFIDENCE_THRESHOLD = 0.62
HEURISTIC_FASTPATH_THRESHOLD = 0.85

SEARCH_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tour": ("tour", "du lich", "tham quan"),
    "villa": ("villa", "biet thu", "biet thu nghi duong"),
}

SORT_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("price", "asc", ("re nhat", "gia thap", "thap nhat", "tang dan", "asc")),
    ("price", "desc", ("mac nhat", "gia cao", "cao nhat", "giam dan", "desc")),
)

SORT_BY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "price": ("gia", "price", "chi phi", "cost"),
    "rating": ("rating", "danh gia", "xep hang"),
}


def _load_slang_replacements() -> dict[str, str]:
    config_path = Path(__file__).resolve().parent / "config" / "slang.json"
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _build_keyword_processor(mapping: dict[str, str]) -> KeywordProcessor:
    processor = KeywordProcessor(case_sensitive=False)
    for keyword, clean_name in mapping.items():
        processor.add_keyword(keyword, clean_name)
    return processor


SLANG_REPLACEMENTS = _load_slang_replacements()
SEARCH_TYPE_PROCESSOR = _build_keyword_processor(
    {
        keyword: search_type
        for search_type, keywords in SEARCH_TYPE_KEYWORDS.items()
        for keyword in keywords
    }
)
SORT_ASC_PROCESSOR = _build_keyword_processor({_normalize: "asc" for _normalize in SORT_PATTERNS[0][2]})
SORT_DESC_PROCESSOR = _build_keyword_processor({_normalize: "desc" for _normalize in SORT_PATTERNS[1][2]})
SORT_PRICE_PROCESSOR = _build_keyword_processor({k: "price" for k in SORT_BY_KEYWORDS["price"]})
SORT_RATING_PROCESSOR = _build_keyword_processor({k: "rating" for k in SORT_BY_KEYWORDS["rating"]})


def normalize_text(text: str) -> str:
    lowered = unidecode(text.lower().strip())
    lowered = re.sub(r"[^a-z0-9/.,\-\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()

    tokens = lowered.split()
    replaced_tokens = [SLANG_REPLACEMENTS.get(token, token) for token in tokens]
    normalized = " ".join(replaced_tokens)
    normalized = re.sub(r"\b(\d{1,2})\s*n\s*(\d{1,2})\s*d\b", r"\1n\2d", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _is_missing_slot_value(key: str, value: Any) -> bool:
    if value is None:
        return True

    default_value = DEFAULT_SLOT_VALUES.get(key)
    if key in {"search_type", "destination", "start_date"}:
        if isinstance(value, str) and not value.strip():
            return True
    if isinstance(default_value, (int, float)) and isinstance(value, (int, float)) and value == default_value:
        return True
    if isinstance(default_value, str) and isinstance(value, str) and value.strip().lower() == default_value.strip().lower():
        return True

    return False


def _compute_overall_confidence(slots: dict[str, Any], scores: dict[str, float]) -> float:
    values = [scores[k] for k in SLOT_KEYS if k in scores and not _is_missing_slot_value(k, slots.get(k))]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _extract_search_type(text: str) -> str | None:
    if SEARCH_TYPE_PROCESSOR.extract_keywords(text):
        if "villa" in text or "biet thu" in text:
            return "villa"
        if "tour" in text or "du lich" in text or "tham quan" in text:
            return "tour"
    return None


def _extract_sorting(text: str) -> tuple[str | None, str | None]:
    sort_by = None
    if SORT_PRICE_PROCESSOR.extract_keywords(text):
        sort_by = "price"
    elif SORT_RATING_PROCESSOR.extract_keywords(text):
        sort_by = "rating"

    if SORT_ASC_PROCESSOR.extract_keywords(text):
        return sort_by or "price", "asc"
    if SORT_DESC_PROCESSOR.extract_keywords(text):
        return sort_by or "price", "desc"
    return sort_by, None


def build_llm_cache_key(message: str, current_slots: dict[str, Any]) -> str:
    payload = f"{message.strip()}|{json.dumps(current_slots, ensure_ascii=False, sort_keys=True, default=str)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def heuristic_extract_with_meta(message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    text = normalize_text(message)
    result: dict[str, Any] = dict(DEFAULT_SLOT_VALUES)
    confidence: dict[str, float] = {}

    _, route_destination = extract_route_cities(text)

    search_type = _extract_search_type(text)
    if search_type:
        result["search_type"] = search_type
        confidence["search_type"] = 0.9

    destination, destination_conf = extract_city_after_cues(text, DESTINATION_CUES)
    if route_destination is not None:
        destination = route_destination
        destination_conf = 0.96

    if destination is None:
        destination = best_city_match(text)
        if destination:
            destination_conf = 0.7

    if destination:
        result["destination"] = destination
        confidence["destination"] = destination_conf

    start_date = parse_date_to_iso(text, message)
    if start_date:
        result["start_date"] = start_date
        confidence["start_date"] = 0.88

    adults, children = extract_people_slots(text)
    if adults is not None:
        result["adults"] = adults
        confidence["adults"] = 0.9
    if children is not None:
        result["children"] = children
        confidence["children"] = 0.9

    duration_date = extract_duration_days(text)
    if duration_date is not None:
        result["duration_date"] = duration_date
        confidence["duration_date"] = 0.9

    sort_by, sort_type = _extract_sorting(text)
    if sort_by:
        result["sort_by"] = sort_by
    if sort_type:
        result["sort_type"] = sort_type
    if sort_by and sort_type:
        confidence["sort_by"] = 0.94
        confidence["sort_type"] = 0.94

    elapsed_ms = (time.perf_counter() - started) * 1000
    meta = {
        "overall_confidence": _compute_overall_confidence(result, confidence),
        "slot_confidence": confidence,
        "latency_ms": round(elapsed_ms, 2),
    }
    return result, meta
