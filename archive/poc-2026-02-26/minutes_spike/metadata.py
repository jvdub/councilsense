from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Tuple


_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_MDY_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_DATE_MONTHNAME_RE = re.compile(
    r"\b(?P<month>[A-Za-z]{3,9})\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\,?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_DATE_DMY_MONTHNAME_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9})\.?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)


def _parse_date_match(text: str) -> Optional[str]:
    """Return ISO date (YYYY-MM-DD) if we can parse a date from text."""

    m = _DATE_ISO_RE.search(text)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    m = _DATE_MONTHNAME_RE.search(text)
    if m:
        month_raw = (m.group("month") or "").strip().lower()
        month = _MONTHS.get(month_raw)
        if month is None:
            month = _MONTHS.get(month_raw[:3])
        if month is not None:
            try:
                dt = datetime(int(m.group("year")), int(month), int(m.group("day")))
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    m = _DATE_DMY_MONTHNAME_RE.search(text)
    if m:
        month_raw = (m.group("month") or "").strip().lower()
        month = _MONTHS.get(month_raw)
        if month is None:
            month = _MONTHS.get(month_raw[:3])
        if month is not None:
            try:
                dt = datetime(int(m.group("year")), int(month), int(m.group("day")))
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    m = _DATE_MDY_SLASH_RE.search(text)
    if m:
        mm = int(m.group(1))
        dd = int(m.group(2))
        yy = int(m.group(3))
        if yy < 100:
            yy = 2000 + yy
        try:
            dt = datetime(yy, mm, dd)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


_LOCATION_HINT_RE = re.compile(
    r"(?i)\b(location|place|where|venue)\s*[:\-]\s*(?P<loc>.+)$"
)


def extract_meeting_metadata(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort heuristics to extract (meeting_date, meeting_location).

    - meeting_date is returned as ISO YYYY-MM-DD when detected.
    - meeting_location is returned as a short human-readable line.

    Designed to be cheap and robust; it does not require external NLP libs.
    """

    if not text:
        return None, None

    # Focus on early header-ish content; PDF extracts can be huge.
    head = text[:20_000]
    lines = [ln.strip() for ln in head.splitlines() if ln.strip()]
    lines = lines[:80]

    meeting_date: Optional[str] = None
    meeting_location: Optional[str] = None

    # Date: try in the first ~20 lines first.
    for ln in lines[:20]:
        meeting_date = _parse_date_match(ln)
        if meeting_date:
            break
    if meeting_date is None:
        # Fall back to searching the full head block.
        meeting_date = _parse_date_match(head)

    def _score_location(candidate: str) -> int:
        c = candidate.strip()
        lc = c.lower()
        score = 0
        if not c:
            return 0
        if len(c) > 140:
            return 0
        if "http" in lc or "www." in lc:
            return 0
        if "agenda" in lc and len(c) < 30:
            score -= 2
        if any(k in lc for k in ["city hall", "council chamber", "council chambers", "chambers", "community center", "municipal", "library"]):
            score += 3
        if re.search(r"\b\d{2,5}\s+\w+", c):
            score += 2
        if any(k in lc for k in ["street", "st.", "avenue", "ave", "road", "rd", "boulevard", "blvd", "drive", "dr", "suite", "room"]):
            score += 1
        if any(k in lc for k in ["call to order", "ordinance", "consent", "adjourn"]):
            score -= 2
        return score

    best_loc: Optional[str] = None
    best_score = 0

    for i, ln in enumerate(lines[:40]):
        m = _LOCATION_HINT_RE.search(ln)
        if m:
            cand = (m.group("loc") or "").strip()
            score = _score_location(cand) + 3
            if score > best_score:
                best_score = score
                best_loc = cand
            continue

        if any(k in ln.lower() for k in ["city hall", "council chambers", "council chamber", "chambers", "community center"]):
            cand = ln
            # Sometimes the address is on the next line.
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if _score_location(nxt) >= 2 and len(nxt) < 80 and not _parse_date_match(nxt):
                    cand = f"{cand} — {nxt}".strip()
            score = _score_location(cand)
            if score > best_score:
                best_score = score
                best_loc = cand

        # Generic address-like line.
        score = _score_location(ln)
        if score > best_score:
            best_score = score
            best_loc = ln

    if best_loc and best_score >= 3:
        meeting_location = best_loc

    return meeting_date, meeting_location
