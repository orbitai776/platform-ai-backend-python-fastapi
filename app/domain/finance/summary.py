from __future__ import annotations

from typing import Any


def build_finance_summary_text(slots: dict[str, Any]) -> str:
    intent = slots.get("intent") or "muc tieu"
    amount = slots.get("amount")
    currency = slots.get("currency") or "VND"
    target_date = slots.get("target_date")

    if isinstance(amount, (int, float)):
        amount_text = f"{amount:,.0f}" if currency == "VND" else f"{amount:,.2f}"
    else:
        amount_text = "N/A"

    if isinstance(target_date, str) and target_date.strip():
        return f"Ban dang thiet lap muc tieu {intent} voi so tien {amount_text} {currency}, han muc tieu {target_date}."
    return f"Ban dang thiet lap muc tieu {intent} voi so tien {amount_text} {currency}."
