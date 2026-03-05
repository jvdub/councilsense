from __future__ import annotations

import re
from dataclasses import dataclass


_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

_QUANTITATIVE_PATTERN = re.compile(
    r"\b\d{1,4}(?:,\d{3})*(?:\.\d+)?\s*(?:"
    r"units?|acres?|percent|%|days?|years?|months?|"
    r"pm|am|miles?|foot|feet|residents?|crossings?|seconds?|"
    r"terms?|phase(?:-two|\s+two)?|rfq|fy\d{4}"
    r")\b",
    flags=re.IGNORECASE,
)
_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_LONG_DATE_PATTERN = re.compile(
    rf"\b(?:{'|'.join(_MONTHS)})\s+\d{{1,2}}(?:,\s*\d{{4}})?\b",
    flags=re.IGNORECASE,
)
_ENTITY_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}\b")

_ENTITY_STOPWORDS = frozenset(
    {
        "City Council",
        "Key Decisions",
        "Key Actions",
        "Notable Topics",
        "Evidence References",
        "Follow Up Actions",
        "Staff Recommendations",
        "Council Deliberation",
        "Agenda Item",
    }
)


@dataclass(frozen=True)
class SpecificityAnchor:
    text: str
    normalized: str
    kind: str
    position: int


def _normalize_anchor(value: str) -> str:
    return " ".join(value.lower().split())


def _collect_matches(*, pattern: re.Pattern[str], text: str, kind: str) -> list[SpecificityAnchor]:
    anchors: list[SpecificityAnchor] = []
    for match in pattern.finditer(text):
        raw = " ".join(match.group(0).split()).strip(" .,:;")
        if not raw:
            continue
        normalized = _normalize_anchor(raw)
        if not normalized:
            continue
        anchors.append(
            SpecificityAnchor(
                text=raw,
                normalized=normalized,
                kind=kind,
                position=match.start(),
            )
        )
    return anchors


def harvest_specificity_anchors(text: str, *, max_anchors: int = 24) -> tuple[SpecificityAnchor, ...]:
    if not text.strip():
        return ()

    collected = [
        *_collect_matches(pattern=_QUANTITATIVE_PATTERN, text=text, kind="quantitative"),
        *_collect_matches(pattern=_ISO_DATE_PATTERN, text=text, kind="date"),
        *_collect_matches(pattern=_LONG_DATE_PATTERN, text=text, kind="date"),
        *_collect_matches(pattern=_ENTITY_PATTERN, text=text, kind="entity"),
    ]

    deduped: dict[tuple[str, str], SpecificityAnchor] = {}
    for anchor in sorted(collected, key=lambda item: (item.position, item.kind, item.normalized)):
        if anchor.kind == "entity" and anchor.text in _ENTITY_STOPWORDS:
            continue
        key = (anchor.kind, anchor.normalized)
        existing = deduped.get(key)
        if existing is None or anchor.position < existing.position:
            deduped[key] = anchor

    prioritized = sorted(
        deduped.values(),
        key=lambda item: (
            0 if item.kind in {"quantitative", "date"} else 1,
            item.position,
            item.normalized,
        ),
    )
    return tuple(prioritized[:max_anchors])


def anchor_present_in_projection(anchor: SpecificityAnchor, projection_text: str) -> bool:
    return anchor.normalized in _normalize_anchor(projection_text)
