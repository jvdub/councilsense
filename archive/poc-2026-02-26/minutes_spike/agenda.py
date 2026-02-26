from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AgendaItem:
    start: int
    end: int
    item_id: str
    title: str
    body_text: str


def _clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


def _looks_like_agenda_title(title: str) -> bool:
    if not title:
        return False
    if re.fullmatch(r"\d+", title):
        return False

    letters = [c for c in title if c.isalpha()]
    if letters:
        upper = sum(1 for c in letters if c.isupper())
        is_all_caps = upper >= len(letters) * 0.7
    else:
        is_all_caps = False

    has_dash = " - " in title
    looks_like_heading = is_all_caps or has_dash
    if looks_like_heading:
        return True

    # Allow common non-dash items (varies by city).
    return bool(
        re.search(
            r"(?i)\b(call to order|pledge|public comments|recognition|minutes|"
            r"resolutions|ordinances|adjournment|agenda review|consent|public hearing)\b",
            title,
        )
    )


def _find_cutoff(items: List[tuple[int, str]]) -> Optional[int]:
    # If we find an explicit ADJOURNMENT in the agenda list, use it as a cutoff
    # to avoid capturing numbered content in later packet attachments.
    cutoff: Optional[int] = None
    for start, title in items:
        if re.search(r"(?i)\badjournment\b", title):
            cutoff = start if cutoff is None else min(cutoff, start)
    return cutoff


def extract_agenda_items(text: str) -> List[AgendaItem]:
    """Best-effort extraction of agenda items (id, title, body_text).

    A3 requirement: identify agenda item headers and associate some body text
    (approximate is OK). We scan early text to avoid obvious attachment false
    positives, then segment body text by header-to-header spans.
    """

    # Agenda lists are typically near the start; scanning the entire packet tends
    # to pick up numbered policy definitions/attachments that aren't agenda items.
    scan_limit = 200_000
    scan = text[:scan_limit]

    # Typical patterns:
    #   14.A. ORDINANCE / PUBLIC HEARING - ...
    #   1.B. DISCUSSION - ...
    #   14. ORDINANCES/PUBLIC HEARINGS
    pattern = re.compile(
        r"(?m)^\s*(?P<id>\d+(?:\.[A-Z])?)\.\s+(?P<title>[^\n]{8,220})$"
    )

    headers: List[tuple[int, int, str, str]] = []  # (start, end, id, title)
    for m in pattern.finditer(scan):
        item_id = m.group("id")
        title = _clean_line(m.group("title"))
        if not _looks_like_agenda_title(title):
            continue
        headers.append((m.start(), m.end(), item_id, title))

    headers.sort(key=lambda x: x[0])

    cutoff = _find_cutoff([(h[0], h[3]) for h in headers])
    agenda_stop: Optional[int] = None
    if cutoff is not None:
        # Keep headers up to and including the first ADJOURNMENT.
        headers = [h for h in headers if h[0] <= cutoff]

        # Prevent the final ADJOURNMENT item from absorbing packet attachments.
        # If we see an EXHIBIT/ATTACHMENT heading after adjournment, cut off there.
        # Otherwise, fall back to the scan limit.
        adj = next((h for h in headers if h[0] == cutoff), None)
        if adj is not None:
            _adj_start, adj_end, _adj_id, _adj_title = adj
            m = re.search(r"(?m)^\s*(EXHIBIT|ATTACHMENT)\s+", text[adj_end:])
            if m:
                agenda_stop = adj_end + m.start()

    items: List[AgendaItem] = []
    for idx, (start, end, item_id, title) in enumerate(headers):
        if idx + 1 < len(headers):
            next_start = headers[idx + 1][0]
        else:
            next_start = min(len(text), scan_limit)
            if agenda_stop is not None:
                next_start = min(next_start, agenda_stop)

        # Body text is the text immediately following the header until the next header.
        body = text[end:next_start]
        body = body.strip("\n ")

        # Keep body_text bounded; the full packet text is stored separately.
        if len(body) > 40_000:
            body = body[:40_000].rstrip() + "\n[...truncated...]"

        items.append(
            AgendaItem(
                start=start,
                end=next_start,
                item_id=item_id,
                title=title,
                body_text=body,
            )
        )

    return items
