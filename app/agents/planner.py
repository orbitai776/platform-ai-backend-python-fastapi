from __future__ import annotations

import logging

from app.agents.base import PlannerAgent
from app.agents.contracts import PlannerDecision
from app.integrations.llm_client import LLMClient

LOGGER = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = (
    "You are a strict routing planner for a multi-domain assistant. "
    "Choose one domain from the allowed list and return JSON only."
)

PLANNER_DECISION_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "planner_decision",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["domain_name", "reason", "confidence"],
                "properties": {
                    "domain_name": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        }
    }
}


class RuleBasedPlannerAgent(PlannerAgent):
    def __init__(self, available_domains: list[str], default_domain: str) -> None:
        self._available_domains = {name.strip().lower() for name in available_domains}
        self._default_domain = default_domain

    async def decide_domain(self, message: str, requested_domain: str | None = None) -> PlannerDecision:
        candidate = (requested_domain or "").strip().lower()
        if candidate and candidate in self._available_domains:
            return PlannerDecision(
                domain_name=candidate,
                reason="selected_from_request",
                confidence=1.0,
            )

        normalized = message.lower()
        if "domain:booking" in normalized and "booking" in self._available_domains:
            return PlannerDecision(
                domain_name="booking",
                reason="explicit_domain_hint",
                confidence=0.98,
            )
        if "domain:inventory" in normalized and "inventory" in self._available_domains:
            return PlannerDecision(
                domain_name="inventory",
                reason="explicit_domain_hint",
                confidence=0.98,
            )
        if "domain:tourist" in normalized and "tourist" in self._available_domains:
            return PlannerDecision(
                domain_name="tourist",
                reason="explicit_domain_hint",
                confidence=0.98,
            )

        booking_keywords = (
            "dat ban",
            "nha hang",
            "quan an",
            "restaurant",
            "ban cho",
            "booking table",
        )
        if any(keyword in normalized for keyword in booking_keywords) and "booking" in self._available_domains:
            return PlannerDecision(
                domain_name="booking",
                reason="matched_booking_keywords",
                confidence=0.88,
            )

        inventory_keywords = (
            "ton kho",
            "kiem ke",
            "dat kho",
            "giu kho",
            "reserve kho",
            "so luong",
            "inventory",
            "stock",
            "warehouse",
        )
        if any(keyword in normalized for keyword in inventory_keywords) and "inventory" in self._available_domains:
            return PlannerDecision(
                domain_name="inventory",
                reason="matched_inventory_keywords",
                confidence=0.86,
            )

        if "tour" in normalized or "villa" in normalized or "du lich" in normalized:
            return PlannerDecision(
                domain_name="tourist",
                reason="matched_tourist_keywords",
                confidence=0.82,
            )

        return PlannerDecision(
            domain_name=self._default_domain,
            reason="fallback_default_domain",
            confidence=0.6,
        )


class LLMPlannerAgent(PlannerAgent):
    def __init__(
        self,
        available_domains: list[str],
        default_domain: str,
        llm_client: LLMClient,
        fallback_planner: RuleBasedPlannerAgent,
    ) -> None:
        self._available_domains = [name.strip().lower() for name in available_domains]
        self._available_domains_set = set(self._available_domains)
        self._default_domain = default_domain
        self._llm_client = llm_client
        self._fallback_planner = fallback_planner

    async def decide_domain(self, message: str, requested_domain: str | None = None) -> PlannerDecision:
        candidate = (requested_domain or "").strip().lower()
        if candidate and candidate in self._available_domains_set:
            return PlannerDecision(
                domain_name=candidate,
                reason="selected_from_request",
                confidence=1.0,
            )

        allowed_domains = ", ".join(self._available_domains)
        system_prompt = (
            f"{PLANNER_SYSTEM_PROMPT} "
            f"Allowed domains: {allowed_domains}. Always choose one from the list."
        )
        try:
            result = await self._llm_client.extract_structured(
                message,
                PLANNER_DECISION_SCHEMA,
                system_prompt=system_prompt,
            )
            content = result.get("content", {})
            if isinstance(content, dict):
                domain_name = str(content.get("domain_name", "")).strip().lower()
                reason = str(content.get("reason", "llm_routing")).strip() or "llm_routing"
                confidence_raw = content.get("confidence", 0.7)
                confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.7
                if domain_name in self._available_domains_set:
                    return PlannerDecision(
                        domain_name=domain_name,
                        reason=reason,
                        confidence=max(0.0, min(1.0, confidence)),
                    )
        except Exception:
            LOGGER.exception("LLM planner failed, falling back to rule-based planner")

        return await self._fallback_planner.decide_domain(message, requested_domain)
