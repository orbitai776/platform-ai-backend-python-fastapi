from __future__ import annotations

from typing import Any

from app.agents.base import DomainAgent
from app.agents.contracts import DomainTurnResult
from app.api.v1.schemas import ChatStatus
from app.domains.tourist.slots import DEFAULT_SLOT_VALUES, REQUIRED_SLOTS, SLOT_QUESTION
from app.domains.tourist.summary import build_tourist_summary_text
from app.services.config import MAX_TURNS


class TouristDomainAgent(DomainAgent):
    domain_name = "tourist"

    def default_slots(self) -> dict[str, Any]:
        return dict(DEFAULT_SLOT_VALUES)

    def merge_slots(self, current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in update.items():
            if key in merged and not self._is_missing_slot_value(key, value):
                merged[key] = value
        return merged

    def process_turn(
        self,
        slots: dict[str, Any],
        turn_count: int,
        stagnation_count: int,
    ) -> DomainTurnResult:
        missing = self.missing_slots(slots)
        status = ChatStatus.completed if not missing else ChatStatus.collecting

        if status == ChatStatus.completed:
            reply = build_tourist_summary_text(slots)
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=reply,
            )

        if turn_count >= MAX_TURNS or stagnation_count >= 2:
            remaining = ", ".join(missing)
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=(
                    "Mình đang thiếu các thông tin sau: "
                    f"{remaining}. Bạn vui lòng gửi đầy đủ các mục này trong một tin nhắn "
                    "để mình hoàn tất bộ lọc nhanh hơn."
                ),
            )

        first_missing = missing[0]
        reply = SLOT_QUESTION.get(first_missing, f"Bạn vui lòng cung cấp {first_missing}.")
        return DomainTurnResult(
            status=status.value,
            missing_slots=missing,
            reply=reply,
        )

    def missing_slots(self, slots: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        for key in REQUIRED_SLOTS:
            if self._is_missing_slot_value(key, slots.get(key)):
                missing.append(key)
        return missing

    def _is_missing_slot_value(self, key: str, value: Any) -> bool:
        if value is None:
            return True
        if key in {"duration_date", "adults", "children"}:
            return isinstance(value, int) and value < 0
        if key == "search_type":
            return not isinstance(value, str) or not value.strip()
        if key in {"destination", "start_date"}:
            return not isinstance(value, str) or not value.strip()
        return False
