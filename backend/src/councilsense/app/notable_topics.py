from __future__ import annotations

import re
from collections.abc import Sequence


_TOPIC_TOKEN_RE = re.compile(r"[a-z][a-z\-]{1,}")
_CIVIC_TOPIC_ANCHOR_TOKENS = frozenset(
    {
        "acquisition",
        "agreement",
        "amendment",
        "annexation",
        "appointments",
        "bond",
        "broadband",
        "board",
        "budget",
        "code",
        "commission",
        "commissions",
        "committee",
        "community",
        "consent",
        "contract",
        "corridor",
        "development",
        "drainage",
        "fee",
        "fees",
        "financial",
        "feedback",
        "fiscal",
        "funding",
        "hearing",
        "housing",
        "improvement",
        "improvements",
        "infrastructure",
        "land",
        "legislative",
        "ordinance",
        "park",
        "parks",
        "permit",
        "plan",
        "planning",
        "procurement",
        "project",
        "rate",
        "rates",
        "recreation",
        "report",
        "resolution",
        "rezoning",
        "road",
        "roadway",
        "safety",
        "school",
        "schools",
        "sewer",
        "sidewalk",
        "site",
        "stormwater",
        "street",
        "subdivision",
        "title",
        "traffic",
        "transfer",
        "transit",
        "transportation",
        "use",
        "utilities",
        "utility",
        "wastewater",
        "water",
        "zoning",
    }
)


def sanitize_notable_topics(items: Sequence[str] | None, *, max_items: int = 5) -> tuple[str, ...]:
    if not items:
        return ()

    cleaned_items: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_topic_label(item)
        if normalized is None:
            continue
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned_items.append(normalized)
        if len(cleaned_items) >= max_items:
            break
    return tuple(cleaned_items)


def _normalize_topic_label(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value).strip(" .,-")
    if not normalized:
        return None

    tokens = tuple(_TOPIC_TOKEN_RE.findall(normalized.lower()))
    if not tokens:
        return None
    if len(tokens) > 6:
        return None
    if not any(token in _CIVIC_TOPIC_ANCHOR_TOKENS for token in tokens):
        return None
    return normalized