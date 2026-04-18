from __future__ import annotations

import re

ADULT_PATTERNS = (
    re.compile(r"\b(\d{1,2})\s*(?:nguoi\s*lon|adult|adults|nl)\b"),
    re.compile(r"\b(\d{1,2})\s*(?:vo\s*chong|vc)\b"),
)

CHILD_PATTERNS = (
    re.compile(r"\b(\d{1,2})\s*(?:tre\s*em|child|children|be|te)\b"),
    re.compile(r"\b(\d{1,2})\s*(?:em\s*be|tre\s*nho|con\s*nho)\b"),
)

TOTAL_PEOPLE_PATTERN = re.compile(r"\b(\d{1,2})\s*(?:nguoi|khach)\b")
DURATION_FULL_PATTERN = re.compile(r"\b(\d{1,2})\s*ngay\s*(\d{1,2})\s*dem\b")
DURATION_DAY_PATTERN = re.compile(r"\b(\d{1,2})\s*ngay\b")
DURATION_COMPACT_PATTERN = re.compile(r"\b(\d{1,2})n\s*(\d{1,2})d\b")


def extract_people_slots(text: str) -> tuple[int | None, int | None]:
    adults: int | None = None
    children: int | None = None

    for pattern in ADULT_PATTERNS:
        match = pattern.search(text)
        if match:
            adults = int(match.group(1))
            break

    for pattern in CHILD_PATTERNS:
        match = pattern.search(text)
        if match:
            children = int(match.group(1))
            break

    total_match = TOTAL_PEOPLE_PATTERN.search(text)
    if total_match:
        total = int(total_match.group(1))
        if adults is None and children is None:
            adults = total
        elif adults is None and children is not None:
            adults = max(total - children, 0)

    if "khong tre em" in text or "khong be" in text:
        children = 0

    return adults, children


def extract_duration_days(text: str) -> int | None:
    compact_match = DURATION_COMPACT_PATTERN.search(text)
    if compact_match:
        return int(compact_match.group(1))

    full_match = DURATION_FULL_PATTERN.search(text)
    if full_match:
        return int(full_match.group(1))

    day_match = DURATION_DAY_PATTERN.search(text)
    if day_match:
        return int(day_match.group(1))

    return None
