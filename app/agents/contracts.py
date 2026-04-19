from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlannerDecision:
    domain_name: str
    reason: str
    confidence: float = 1.0


@dataclass(frozen=True)
class SlotExtractionResult:
    slot_update: dict[str, Any]
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentContext:
    message: str
    turn_count: int
    history: list[dict[str, str]]
    current_slots: dict[str, Any]
    llm_cache: dict[str, dict[str, Any]] | None


@dataclass(frozen=True)
class DomainTurnResult:
    status: str
    missing_slots: list[str]
    reply: str
