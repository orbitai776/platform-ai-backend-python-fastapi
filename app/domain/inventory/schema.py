from __future__ import annotations

INVENTORY_SYSTEM_PROMPT = (
    "You are a strict warehouse reservation slot extraction engine. Extract values from user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do not invent facts."
)

INVENTORY_SLOT_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "json_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "item_name",
                    "quantity",
                    "warehouse",
                    "booking_date",
                    "booking_time",
                ],
                "properties": {
                    "item_name": {"type": ["string", "null"], "default": None},
                    "quantity": {"type": ["integer", "null"], "default": None},
                    "warehouse": {"type": ["string", "null"], "default": None},
                    "booking_date": {"type": ["string", "null"], "format": "date", "default": None},
                    "booking_time": {"type": ["string", "null"], "format": "time", "default": None},
                },
            },
        }
    }
}
