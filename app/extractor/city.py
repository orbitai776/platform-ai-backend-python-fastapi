from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flashtext import KeywordProcessor
from rapidfuzz import fuzz, process
from underthesea import word_tokenize
from unidecode import unidecode

DESTINATION_CUES = ("di", "den", "du lich", "tham quan")
START_POINT_CUES = ("xuat phat tu", "khoi hanh tu", "bay tu", "tu")

ROUTE_FROM_TO_PATTERN = re.compile(
    r"\b(?:xuat phat tu|khoi hanh tu|bay tu|tu)\s+([a-z][a-z\s]{1,40}?)\s+(?:den|toi)\s+([a-z][a-z\s]{1,40})(?=$|[,.!;]|\s(?:voi|ngay|thang|gia|budget)\b)"
)
ROUTE_DEST_THEN_FROM_PATTERN = re.compile(
    r"\b(?:di|den|toi)\s+([a-z][a-z\s]{1,40}?)\s+(?:tu|xuat phat tu|khoi hanh tu|bay tu)\s+([a-z][a-z\s]{1,40})(?=$|[,.!;]|\s(?:voi|ngay|thang|gia|budget)\b)"
)

CITY_FUZZY_SCORE_CUTOFF = 84
MAX_CITY_NGRAM = 3
MAX_CITY_TOKEN_WINDOW = 5
MAX_CITY_CANDIDATES = 24

CONNECTOR_TOKENS = {
    "di",
    "den",
    "toi",
    "tu",
    "voi",
    "khoi",
    "hanh",
    "ngay",
    "thang",
    "nam",
    "gia",
    "ngan",
    "sach",
    "re",
    "mac",
}


def _tokenize_vi(text: str) -> list[str]:
    segmented = word_tokenize(text, format="text")
    cleaned = segmented.replace("_", " ")
    return [token for token in cleaned.split() if token]


def _normalize_text(text: str) -> str:
    lowered = unidecode(text.lower().strip())
    lowered = re.sub(r"[^a-z0-9/.,\-\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _load_city_aliases() -> dict[str, list[str]]:
    config_path = Path(__file__).resolve().parent / "config" / "cities.json"
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}

    result: dict[str, list[str]] = {}
    for canonical, aliases in data.items():
        if not isinstance(canonical, str) or not isinstance(aliases, list):
            continue
        valid_aliases = [alias for alias in aliases if isinstance(alias, str)]
        if valid_aliases:
            result[canonical] = valid_aliases
    return result


def _build_keyword_processor(mapping: dict[str, str]) -> KeywordProcessor:
    processor = KeywordProcessor(case_sensitive=False)
    for keyword, clean_name in mapping.items():
        processor.add_keyword(keyword, clean_name)
    return processor


def _build_city_lookup(city_aliases: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in city_aliases.items():
        for alias in aliases:
            lookup[_normalize_text(alias)] = canonical
    return lookup


CITY_ALIASES = _load_city_aliases()
CITY_LOOKUP = _build_city_lookup(CITY_ALIASES)
CITY_ALIAS_KEYS = tuple(CITY_LOOKUP.keys())
CITY_KEYWORD_PROCESSOR = _build_keyword_processor({alias: canonical for alias, canonical in CITY_LOOKUP.items()})

CITY_ALIAS_BY_FIRST_TOKEN: dict[str, list[str]] = {}
for alias in CITY_ALIAS_KEYS:
    token = alias.split()[0]
    CITY_ALIAS_BY_FIRST_TOKEN.setdefault(token, []).append(alias)

DEST_CUE_PROCESSOR = _build_keyword_processor({cue: cue for cue in DESTINATION_CUES})
START_CUE_PROCESSOR = _build_keyword_processor({cue: cue for cue in START_POINT_CUES})


def best_city_match(fragment: str) -> str | None:
    normalized_fragment = _normalize_text(fragment)
    normalized_fragment = re.sub(r"[.,;:-]+", " ", normalized_fragment)
    normalized_fragment = re.sub(r"\s+", " ", normalized_fragment).strip()
    if not normalized_fragment:
        return None

    exact_matches = CITY_KEYWORD_PROCESSOR.extract_keywords(normalized_fragment)
    if exact_matches:
        return exact_matches[0]

    tokens = normalized_fragment.split()
    if not tokens:
        return None

    token_window = tokens[:MAX_CITY_TOKEN_WINDOW]
    ngrams: list[str] = []
    max_size = min(MAX_CITY_NGRAM, len(token_window))
    for size in range(max_size, 0, -1):
        for i in range(len(token_window) - size + 1):
            ngrams.append(" ".join(token_window[i : i + size]))

    for gram in ngrams:
        if any(ch.isdigit() for ch in gram):
            continue
        if len(gram) < 4:
            continue

        first_token = gram.split()[0]
        candidates = CITY_ALIAS_BY_FIRST_TOKEN.get(first_token)
        if not candidates:
            if len(gram.split()) < 2:
                continue
            candidates = list(CITY_ALIAS_KEYS[:MAX_CITY_CANDIDATES])
        else:
            candidates = candidates[:MAX_CITY_CANDIDATES]

        match = process.extractOne(gram, candidates, scorer=fuzz.WRatio, score_cutoff=CITY_FUZZY_SCORE_CUTOFF)
        if match:
            matched_alias = match[0]
            return CITY_LOOKUP[matched_alias]

    return None


def _extract_city_by_cue(text: str, cue_processor: KeywordProcessor) -> tuple[str | None, float]:
    cue_matches = cue_processor.extract_keywords(text, span_info=True)
    if not cue_matches:
        return None, 0.0

    for _, _, cue_end in cue_matches:
        trailing = text[cue_end:].strip()
        if not trailing:
            continue

        trailing_tokens = _tokenize_vi(trailing)
        candidate_tokens: list[str] = []
        for token in trailing_tokens:
            if token in CONNECTOR_TOKENS and candidate_tokens:
                break
            if token in CONNECTOR_TOKENS and not candidate_tokens:
                continue
            candidate_tokens.append(token)
            if len(candidate_tokens) >= MAX_CITY_TOKEN_WINDOW:
                break

        candidate = " ".join(candidate_tokens)
        city = best_city_match(candidate)
        if city:
            return city, 0.93

    return None, 0.0


def extract_city_after_cues(text: str, cues: tuple[str, ...]) -> tuple[str | None, float]:
    cue_processor = DEST_CUE_PROCESSOR if cues is DESTINATION_CUES else START_CUE_PROCESSOR
    city, confidence = _extract_city_by_cue(text, cue_processor)
    if city:
        return city, confidence

    for cue in cues:
        idx = text.find(cue)
        if idx == -1:
            continue
        trailing = text[idx + len(cue) :].strip()
        if not trailing:
            continue
        trailing_tokens = [t for t in _tokenize_vi(trailing) if t not in CONNECTOR_TOKENS]
        city = best_city_match(" ".join(trailing_tokens[:4]))
        if city:
            return city, 0.78

    return None, 0.0


def extract_route_cities(text: str) -> tuple[str | None, str | None]:
    from_to_match = ROUTE_FROM_TO_PATTERN.search(text)
    if from_to_match:
        start_candidate = from_to_match.group(1).strip()
        destination_candidate = from_to_match.group(2).strip()
        return best_city_match(start_candidate), best_city_match(destination_candidate)

    dest_then_from_match = ROUTE_DEST_THEN_FROM_PATTERN.search(text)
    if dest_then_from_match:
        destination_candidate = dest_then_from_match.group(1).strip()
        start_candidate = dest_then_from_match.group(2).strip()
        return best_city_match(start_candidate), best_city_match(destination_candidate)

    return None, None
