from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agents.contracts import AgentContext, DomainTurnResult, PlannerDecision, SlotExtractionResult


class PlannerAgent(ABC):
    @abstractmethod
    async def decide_domain(self, message: str, requested_domain: str | None = None) -> PlannerDecision:
        raise NotImplementedError


class SlotFillingAgent(ABC):
    @abstractmethod
    async def extract(self, context: AgentContext) -> SlotExtractionResult:
        raise NotImplementedError


class DomainAgent(ABC):
    domain_name: str

    @abstractmethod
    def default_slots(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def merge_slots(self, current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def process_turn(
        self,
        slots: dict[str, Any],
        turn_count: int,
        stagnation_count: int,
    ) -> DomainTurnResult:
        raise NotImplementedError

    @abstractmethod
    def missing_slots(self, slots: dict[str, Any]) -> list[str]:
        raise NotImplementedError
