from __future__ import annotations

import logging
from typing import Any

from app.agents.base import SlotFillingAgent
from app.agents.contracts import AgentContext, SlotExtractionResult
from app.domain.booking.heuristic import (
    HEURISTIC_FASTPATH_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    build_llm_cache_key,
    heuristic_extract_with_meta,
)
from app.domain.booking.schema import BOOKING_SLOT_SCHEMA, BOOKING_SYSTEM_PROMPT
from app.domain.booking.slots import BookingSlotData
from app.integrations.llm_client import LLMClient

LOGGER = logging.getLogger(__name__)


class BookingSlotFillingAgent(SlotFillingAgent):
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def extract(self, context: AgentContext) -> SlotExtractionResult:
        cache_key = build_llm_cache_key(context.message, context.current_slots)
        if context.llm_cache is not None and cache_key in context.llm_cache:
            return SlotExtractionResult(
                slot_update=context.llm_cache[cache_key],
                source="cache",
                metadata={"cache_key": cache_key},
            )

        heuristic_result, heuristic_meta = heuristic_extract_with_meta(context.message)
        heuristic_conf = float(heuristic_meta.get("overall_confidence", 0.0))

        if heuristic_conf >= HEURISTIC_FASTPATH_THRESHOLD:
            if context.llm_cache is not None:
                context.llm_cache[cache_key] = heuristic_result
            return SlotExtractionResult(
                slot_update=heuristic_result,
                source="heuristic_fastpath",
                metadata=heuristic_meta,
            )

        try:
            extracted = await self._llm_client.extract_structured(
                context.message,
                BOOKING_SLOT_SCHEMA,
                system_prompt=BOOKING_SYSTEM_PROMPT,
                validate_slot_data=True,
                slot_validator=self._validate_slots,
            )
            content = extracted.get("content", {})
            if isinstance(content, dict):
                merged = dict(heuristic_result)
                for key, value in content.items():
                    if value is not None:
                        merged[key] = value
                if context.llm_cache is not None:
                    context.llm_cache[cache_key] = merged
                return SlotExtractionResult(
                    slot_update=merged,
                    source="llm",
                    metadata={
                        **heuristic_meta,
                        "usage": extracted.get("usage"),
                    },
                )
        except Exception:
            LOGGER.exception("Booking LLM extraction failed, using heuristic fallback")

        if heuristic_conf < LOW_CONFIDENCE_THRESHOLD:
            LOGGER.warning("Low-confidence booking extraction", extra={"heuristic_confidence": heuristic_conf})

        if context.llm_cache is not None:
            context.llm_cache[cache_key] = heuristic_result
        return SlotExtractionResult(
            slot_update=heuristic_result,
            source="heuristic_fallback",
            metadata=heuristic_meta,
        )

    def _validate_slots(self, content: dict[str, Any]) -> dict[str, Any]:
        return BookingSlotData.model_validate(content).model_dump(mode="python")