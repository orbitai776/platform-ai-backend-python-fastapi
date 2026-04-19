from __future__ import annotations

import logging
from typing import Any, Protocol

from app.api.v1.schemas import ChatStatus
from app.domain.tourist.heuristic import (
    HEURISTIC_FASTPATH_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    build_llm_cache_key,
)
from app.integrations.llm_adapter import call_extractor

LOGGER = logging.getLogger(__name__)


class SlotServiceDefinition(Protocol):
    required_slots: list[str]
    slot_questions: dict[str, str]
    slot_schema: dict[str, Any]
    system_prompt: str

    def default_slots(self) -> dict[str, Any]: ...

    def is_missing_slot_value(self, key: str, value: Any) -> bool: ...

    def heuristic_extractor_with_meta(self, message: str) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def slot_validator(self, content: dict[str, Any]) -> dict[str, Any]: ...


def default_slots(service_def: SlotServiceDefinition) -> dict[str, Any]:
    return service_def.default_slots()


def merge_slots(current: dict[str, Any], update: dict[str, Any], service_def: SlotServiceDefinition) -> dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        if key in merged and not service_def.is_missing_slot_value(key, value):
            merged[key] = value
    return merged


def missing_slots(slots: dict[str, Any], service_def: SlotServiceDefinition) -> list[str]:
    missing: list[str] = []
    for key in service_def.required_slots:
        value = slots.get(key)
        if service_def.is_missing_slot_value(key, value):
            missing.append(key)
    return missing


def status_from_missing(missing: list[str]) -> ChatStatus:
    return ChatStatus.completed if not missing else ChatStatus.collecting


def next_question(missing: list[str], service_def: SlotServiceDefinition) -> str:
    if not missing:
        return "Thông tin đã đầy đủ."
    first_missing = missing[0]
    return service_def.slot_questions.get(first_missing, f"Bạn vui lòng cung cấp {first_missing}.")


async def extract_slot_update_with_cache(
    message: str,
    current_slots: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
    service_def: SlotServiceDefinition,
) -> dict[str, Any]:
    cache_key = build_llm_cache_key(message, current_slots)
    if llm_cache is not None and cache_key in llm_cache:
        return llm_cache[cache_key]

    heuristic_result, heuristic_meta = service_def.heuristic_extractor_with_meta(message)
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
        extractor_result = await call_extractor(
            message,
            service_def.slot_schema,
            validate_slot_data=True,
            system_prompt=service_def.system_prompt,
            slot_validator=service_def.slot_validator,
        )
        content = extractor_result.get("content", {})
        if isinstance(content, dict):
            merged = merge_slots(heuristic_result, content, service_def)
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