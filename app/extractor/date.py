from __future__ import annotations

import re

from dateparser import parse as parse_date

DATE_NUMERIC_PATTERN = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")

DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "DATE_ORDER": "DMY",
    "PREFER_DAY_OF_MONTH": "first",
}

RELATIVE_DATE_FALLBACKS = {
    "mai": "ngay mai",
    "mot": "ngay mot",
    "hom nay": "hom nay",
    "tuan sau": "tuan sau",
}


def _needs_date_parse(text: str) -> bool:
    normalized = text.lower()
    if DATE_NUMERIC_PATTERN.search(normalized):
        return True
    return any(marker in normalized for marker in ("ngay", "thang", "nam", "mai", "mot", "tuan sau"))


def parse_date_to_iso(raw_value: str, original_text: str) -> str | None:
    if not _needs_date_parse(raw_value):
        return None

    date_match = DATE_NUMERIC_PATTERN.search(raw_value)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else None
        if year is not None and year < 100:
            year += 2000
        date_candidate = f"{day:02d}/{month:02d}" if year is None else f"{day:02d}/{month:02d}/{year:04d}"
        parsed = parse_date(date_candidate, languages=["vi", "en"], settings=DATEPARSER_SETTINGS)
        if parsed:
            return parsed.strftime("%Y-%m-%d")

    parsed_vi = parse_date(original_text, languages=["vi"], settings=DATEPARSER_SETTINGS)
    if parsed_vi:
        return parsed_vi.strftime("%Y-%m-%d")

    parsed_normalized = parse_date(raw_value, languages=["vi", "en"], settings=DATEPARSER_SETTINGS)
    if parsed_normalized:
        return parsed_normalized.strftime("%Y-%m-%d")

    for marker, phrase in RELATIVE_DATE_FALLBACKS.items():
        if marker in raw_value:
            parsed_relative = parse_date(phrase, languages=["vi"], settings=DATEPARSER_SETTINGS)
            if parsed_relative:
                return parsed_relative.strftime("%Y-%m-%d")

    return None
