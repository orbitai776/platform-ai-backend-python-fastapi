from __future__ import annotations

from typing import Any

from app.agents.base import DomainAgent
from app.agents.contracts import DomainTurnResult
from app.api.v1.schemas import ChatStatus
from app.application.config import MAX_TURNS
from app.domain.finance.slots import DEFAULT_SLOT_VALUES, REQUIRED_SLOTS, SLOT_QUESTION
from app.domain.finance.summary import build_finance_summary_text


class FinanceDomainAgent(DomainAgent):
    domain_name = "finance"

    def default_slots(self) -> dict[str, Any]:
        return dict(DEFAULT_SLOT_VALUES)

    def merge_slots(self, current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in update.items():
            if key in merged and not self._is_missing_slot_value(key, value):
                merged[key] = value
        return merged

    def process_turn(self, slots: dict[str, Any], turn_count: int, stagnation_count: int) -> DomainTurnResult:
        missing = self.missing_slots(slots)
        status = ChatStatus.completed if not missing else ChatStatus.collecting

        if status == ChatStatus.completed:
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=build_finance_summary_text(slots),
            )

        if turn_count >= MAX_TURNS or stagnation_count >= 2:
            remaining = ", ".join(missing)
            return DomainTurnResult(
                status=status.value,
                missing_slots=missing,
                reply=(
                    "Minh dang thieu cac thong tin sau: "
                    f"{remaining}. Ban gui day du trong mot tin nhan giup minh nhe."
                ),
            )

        first_missing = missing[0]
        return DomainTurnResult(
            status=status.value,
            missing_slots=missing,
            reply=SLOT_QUESTION.get(first_missing, f"Ban vui long cung cap {first_missing}."),
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
        if key == "intent":
            return not isinstance(value, str) or not value.strip()
        if key == "amount":
            return not isinstance(value, (int, float)) or value <= 0
        if key == "currency":
            return not isinstance(value, str) or not value.strip()
        return False