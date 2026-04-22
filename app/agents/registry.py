from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agents.base import DomainAgent, PlannerAgent, SlotFillingAgent
from app.agents.planner import LLMPlannerAgent, RuleBasedPlannerAgent
from app.domain.booking.agent import BookingDomainAgent
from app.domain.booking.extractor import BookingSlotFillingAgent
from app.domain.booking.schema import BOOKING_SLOT_SCHEMA, BOOKING_SYSTEM_PROMPT
from app.domain.booking.slots import BookingSlotData
from app.domain.inventory.agent import InventoryDomainAgent
from app.domain.inventory.extractor import InventorySlotFillingAgent
from app.domain.inventory.schema import INVENTORY_SLOT_SCHEMA, INVENTORY_SYSTEM_PROMPT
from app.domain.inventory.slots import InventorySlotData
from app.domain.tourist.agent import TouristDomainAgent
from app.domain.tourist.extractor import TouristSlotFillingAgent
from app.domain.tourist.schema import TOURIST_SLOT_SCHEMA, TOURIST_SYSTEM_PROMPT
from app.domain.tourist.slots import TouristSlotData
from app.integrations.llm_client import get_default_llm_client

DEFAULT_DOMAIN_NAME = "tourist"


@dataclass(frozen=True)
class DomainAgentBundle:
    domain_agent: DomainAgent
    slot_filling_agent: SlotFillingAgent


@dataclass(frozen=True)
class DomainExtractionConfig:
    system_prompt: str
    default_schema: dict[str, Any]
    slot_validator: Callable[[dict[str, Any]], dict[str, Any]]


class AgentRegistry:
    def __init__(
        self,
        planner_agent: PlannerAgent,
        domain_bundles: dict[str, DomainAgentBundle],
        extraction_configs: dict[str, DomainExtractionConfig],
    ) -> None:
        self._planner_agent = planner_agent
        self._domain_bundles = domain_bundles
        self._extraction_configs = extraction_configs

    @property
    def planner(self) -> PlannerAgent:
        return self._planner_agent

    def list_domains(self) -> list[str]:
        return sorted(self._domain_bundles.keys())

    def get_bundle(self, domain_name: str) -> DomainAgentBundle:
        selected = domain_name.strip().lower()
        bundle = self._domain_bundles.get(selected)
        if bundle is None:
            available = ", ".join(self.list_domains())
            raise ValueError(f"Domain '{selected}' không tồn tại. Các domain hỗ trợ: {available}")
        return bundle

    def get_extraction_config(self, domain_name: str) -> DomainExtractionConfig:
        selected = domain_name.strip().lower()
        config = self._extraction_configs.get(selected)
        if config is None:
            available = ", ".join(self.list_domains())
            raise ValueError(f"Domain '{selected}' không tồn tại. Các domain hỗ trợ: {available}")
        return config


_DEFAULT_REGISTRY: AgentRegistry | None = None


def _validate_inventory_slots(content: dict[str, Any]) -> dict[str, Any]:
    return InventorySlotData.model_validate(content).model_dump(mode="python")


def _validate_tourist_slots(content: dict[str, Any]) -> dict[str, Any]:
    return TouristSlotData.model_validate(content).model_dump(mode="python")


def _validate_booking_slots(content: dict[str, Any]) -> dict[str, Any]:
    return BookingSlotData.model_validate(content).model_dump(mode="python")


def get_agent_registry() -> AgentRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is not None:
        return _DEFAULT_REGISTRY

    llm_client = get_default_llm_client()
    domain_bundles = {
        "booking": DomainAgentBundle(
            domain_agent=BookingDomainAgent(),
            slot_filling_agent=BookingSlotFillingAgent(llm_client=llm_client),
        ),
        "inventory": DomainAgentBundle(
            domain_agent=InventoryDomainAgent(),
            slot_filling_agent=InventorySlotFillingAgent(llm_client=llm_client),
        ),
        "tourist": DomainAgentBundle(
            domain_agent=TouristDomainAgent(),
            slot_filling_agent=TouristSlotFillingAgent(llm_client=llm_client),
        ),
    }
    extraction_configs = {
        "booking": DomainExtractionConfig(
            system_prompt=BOOKING_SYSTEM_PROMPT,
            default_schema=BOOKING_SLOT_SCHEMA,
            slot_validator=_validate_booking_slots,
        ),
        "inventory": DomainExtractionConfig(
            system_prompt=INVENTORY_SYSTEM_PROMPT,
            default_schema=INVENTORY_SLOT_SCHEMA,
            slot_validator=_validate_inventory_slots,
        ),
        "tourist": DomainExtractionConfig(
            system_prompt=TOURIST_SYSTEM_PROMPT,
            default_schema=TOURIST_SLOT_SCHEMA,
            slot_validator=_validate_tourist_slots,
        ),
    }
    fallback_planner = RuleBasedPlannerAgent(
        available_domains=list(domain_bundles.keys()),
        default_domain=DEFAULT_DOMAIN_NAME,
    )
    planner = LLMPlannerAgent(
        available_domains=list(domain_bundles.keys()),
        default_domain=DEFAULT_DOMAIN_NAME,
        llm_client=llm_client,
        fallback_planner=fallback_planner,
    )
    _DEFAULT_REGISTRY = AgentRegistry(
        planner_agent=planner,
        domain_bundles=domain_bundles,
        extraction_configs=extraction_configs,
    )
    return _DEFAULT_REGISTRY
