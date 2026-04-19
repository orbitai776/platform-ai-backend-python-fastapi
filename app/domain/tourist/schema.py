from __future__ import annotations

TOURIST_SYSTEM_PROMPT = (
    "You are a strict slot extraction engine for tourist search. Extract values from user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do not invent facts."
)

TOURIST_SLOT_SCHEMA = {
    "text": {
        "format": {
            "type": "json_schema",
            "name": "json_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "search_type",
                    "destination",
                    "start_date",
                    "duration_date",
                    "adults",
                    "children",
                    "sort_by",
                    "sort_type",
                ],
                "properties": {
                    "search_type": {
                        "type": ["string", "null"],
                        "enum": ["tour", "villa", ""],
                        "default": None,
                    },
                    "destination": {"type": ["string", "null"], "default": None},
                    "start_date": {"type": ["string", "null"], "format": "date", "default": None},
                    "duration_date": {"type": ["integer", "null"], "default": None},
                    "adults": {"type": ["integer", "null"], "default": None},
                    "children": {"type": ["integer", "null"], "default": None},
                    "sort_by": {
                        "type": "string",
                        "enum": ["price", "rating"],
                        "default": "price",
                    },
                    "sort_type": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "default": "asc",
                    },
                },
            },
        }
    }
}