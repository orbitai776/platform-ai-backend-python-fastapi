from __future__ import annotations

from typing import Any

from app.agents.base import DomainAgent
from app.agents.contracts import DomainTurnResult
from app.api.v1.schemas import ChatStatus
from app.application.config import MAX_TURNS
from app.domain.booking.slots import DEFAULT_SLOT_VALUES, REQUIRED_SLOTS, SLOT_QUESTION
from app.domain.booking.summary import build_booking_summary_text


class BookingDomainAgent(DomainAgent):
    domain_name = "booking"

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
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=build_booking_summary_text(slots),
            )

        if turn_count >= MAX_TURNS or stagnation_count >= 2:
            remaining = ", ".join(missing)
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=(
                    "Mình đang thiếu các thông tin sau: "
                    f"{remaining}. Bạn gửi đầy đủ trong một tin nhắn giúp mình nhé."
                ),
            )

        first_missing = missing[0]
        return DomainTurnResult(
            status=status.value,
            missing_slots=missing,
            reply=SLOT_QUESTION.get(first_missing, f"Bạn vui lòng cung cấp {first_missing}."),
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
        if key in {"restaurant_name", "area", "booking_date", "booking_time", "seating_preference"}:
            return not isinstance(value, str) or not value.strip()
        if key == "party_size":
            return not isinstance(value, int) or value <= 0
        return False