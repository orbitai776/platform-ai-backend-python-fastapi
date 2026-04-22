from __future__ import annotations

BOOKING_SYSTEM_PROMPT = (
    "You are a strict restaurant table booking slot extraction engine. Extract values from user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do not invent facts."
)

BOOKING_SLOT_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "json_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "restaurant_name",
                    "area",
                    "booking_date",
                    "booking_time",
                    "party_size",
                    "seating_preference",
                ],
                "properties": {
                    "restaurant_name": {"type": ["string", "null"], "default": None},
                    "area": {"type": ["string", "null"], "default": None},
                    "booking_date": {"type": ["string", "null"], "format": "date", "default": None},
                    "booking_time": {"type": ["string", "null"], "format": "time", "default": None},
                    "party_size": {"type": ["integer", "null"], "default": None},
                    "seating_preference": {
                        "type": "string",
                        "enum": ["indoor", "outdoor", "private_room"],
                        "default": "indoor",
                    },
                },
            },
        }
    }
}