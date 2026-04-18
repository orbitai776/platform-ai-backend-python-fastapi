from __future__ import annotations

FINANCE_SYSTEM_PROMPT = (
    "You are a strict finance slot extraction engine. Extract values from user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do not invent facts."
)

FINANCE_SLOT_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "json_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["intent", "amount", "currency", "target_date"],
                "properties": {
                    "intent": {
                        "type": ["string", "null"],
                        "enum": ["expense", "saving", "investment", ""],
                        "default": None,
                    },
                    "amount": {"type": ["number", "null"], "default": None},
                    "currency": {
                        "type": "string",
                        "enum": ["VND", "USD"],
                        "default": "VND",
                    },
                    "target_date": {"type": ["string", "null"], "format": "date", "default": None},
                },
            },
        }
    }
}