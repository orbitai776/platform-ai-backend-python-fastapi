from __future__ import annotations

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
