from __future__ import annotations

import logging
from typing import Any

from app.ai_service import call_extractor
from app.extractor.heuristic import (
    HEURISTIC_FASTPATH_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    build_llm_cache_key,
    heuristic_extract_with_meta,
)
from app.schemas import ChatStatus, DEFAULT_SLOT_VALUES, REQUIRED_SLOTS, SLOT_QUESTION, SLOT_SCHEMA

LOGGER = logging.getLogger(__name__)


def default_slots() -> dict[str, Any]:
    return dict(DEFAULT_SLOT_VALUES)


def _is_missing_slot_value(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key in {"duration_date", "adults", "children"}:
        return isinstance(value, int) and value < 0
    if key == "search_type":
        return not isinstance(value, str) or not value.strip()
    if key in {"destination", "start_date"}:
        return not isinstance(value, str) or not value.strip()
    return isinstance(value, str) and not value.strip()


def merge_slots(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        if key in merged and not _is_missing_slot_value(key, value):
            merged[key] = value
    return merged


def missing_slots(slots: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_SLOTS:
        value = slots.get(key)
        if _is_missing_slot_value(key, value):
            missing.append(key)
    return missing


def status_from_missing(missing: list[str]) -> ChatStatus:
    return ChatStatus.completed if not missing else ChatStatus.collecting


def next_question(missing: list[str]) -> str:
    if not missing:
        return "Thông tin đã đầy đủ."
    first_missing = missing[0]
    return SLOT_QUESTION.get(first_missing, f"Bạn vui lòng cung cấp {first_missing}.")


def heuristic_extract_slots(message: str) -> dict[str, Any]:
    result, _ = heuristic_extract_with_meta(message)
    return result


async def extract_slot_update(message: str, current_slots: dict[str, Any]) -> dict[str, Any]:
    return await extract_slot_update_with_cache(message, current_slots, llm_cache=None)


async def extract_slot_update_with_cache(
    message: str,
    current_slots: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    cache_key = build_llm_cache_key(message, current_slots)
    if llm_cache is not None and cache_key in llm_cache:
        return llm_cache[cache_key]

    heuristic_result, heuristic_meta = heuristic_extract_with_meta(message)
    heuristic_conf = float(heuristic_meta.get("overall_confidence", 0.0))
    LOGGER.debug(
        "Heuristic extraction completed",
        extra={
            "heuristic_confidence": heuristic_conf,
            "heuristic_latency_ms": heuristic_meta.get("latency_ms"),
        },
    )

    if heuristic_conf >= HEURISTIC_FASTPATH_THRESHOLD:
        if llm_cache is not None:
            llm_cache[cache_key] = heuristic_result
        return heuristic_result

    try:
        extractor_result = await call_extractor(message, SLOT_SCHEMA, validate_slot_data=True)
        content = extractor_result.get("content", {})
        if isinstance(content, dict):
            merged = merge_slots(heuristic_result, content)
            if llm_cache is not None:
                llm_cache[cache_key] = merged
            return merged
    except Exception:
        LOGGER.exception("LLM extraction failed, using heuristic fallback")

    if heuristic_conf < LOW_CONFIDENCE_THRESHOLD:
        LOGGER.warning("Low-confidence heuristic extraction", extra={"heuristic_confidence": heuristic_conf})

    if llm_cache is not None:
        llm_cache[cache_key] = heuristic_result
    return heuristic_result
