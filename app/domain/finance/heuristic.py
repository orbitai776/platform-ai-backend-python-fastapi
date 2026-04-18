from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.domain.finance.slots import DEFAULT_SLOT_VALUES

_INTENT_MAP = {
    "chi tieu": "expense",
    "expense": "expense",
    "tiet kiem": "saving",
    "saving": "saving",
    "dau tu": "investment",
    "investment": "investment",
}

_AMOUNT_PATTERN = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(trieu|k|nghin|usd|vnd)?\b", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def build_llm_cache_key(message: str, current_slots: dict[str, Any]) -> str:
    return f"finance::{message.strip().lower()}::{str(sorted(current_slots.items()))}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def heuristic_extract_with_meta(message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = normalize_text(message)
    result = dict(DEFAULT_SLOT_VALUES)
    confidence: dict[str, float] = {}

    for keyword, intent in _INTENT_MAP.items():
        if keyword in text:
            result["intent"] = intent
            confidence["intent"] = 0.9
            break

    amount_match = _AMOUNT_PATTERN.search(text)
    if amount_match:
        raw = amount_match.group(1).replace(",", ".")
        unit = (amount_match.group(2) or "").lower()
        value = float(raw)
        if unit == "trieu":
            value *= 1_000_000
            result["currency"] = "VND"
        elif unit == "k" or unit == "nghin":
            value *= 1_000
            result["currency"] = "VND"
        elif unit == "usd":
            result["currency"] = "USD"
        elif unit == "vnd":
            result["currency"] = "VND"
        result["amount"] = value
        confidence["amount"] = 0.88

    date_match = _DATE_PATTERN.search(text)
    if date_match:
        try:
            result["target_date"] = date.fromisoformat(date_match.group(1)).isoformat()
            confidence["target_date"] = 0.9
        except ValueError:
            pass

    if "usd" in text and result.get("currency") == "VND":
        result["currency"] = "USD"
    if "vnd" in text:
        result["currency"] = "VND"

    filled_scores = list(confidence.values())
    overall = sum(filled_scores) / len(filled_scores) if filled_scores else 0.0
    return result, {
        "overall_confidence": overall,
        "slot_confidence": confidence,
        "latency_ms": 0.1,
    }
