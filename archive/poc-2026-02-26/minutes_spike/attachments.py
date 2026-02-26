from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Attachment:
    start: int
    end: int
    attachment_id: str
    title: str
    type_guess: Optional[str]
    body_text: str


def _clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


def guess_attachment_type(text: str) -> Optional[str]:
    """Heuristic attachment type guess.

    Returns one of: plat, staff_report, policy, map, exhibit (fallback).
    """

    t = text.casefold()

    plat_markers = (
        " plat",
        "legal description",
        "township",
        "range ",
        "range,",
        "salt lake base",
        "meridian",
        "metes and bounds",
        "subdivision",
    )
    staff_markers = (
        "staff report",
        "planning commission",
        "recommendation",
        "background",
        "analysis",
        "fiscal impact",
        "attachments:",
    )
    policy_markers = (
        "policy",
        "definitions",
        "section ",
        "chapter ",
        "ordinance",
        "code ",
    )
    map_markers = (
        "vicinity map",
        "zoning map",
        "map ",
        "map:",
    )

    if any(m in t for m in plat_markers):
        return "plat"
    if any(m in t for m in staff_markers):
        return "staff_report"
    if any(m in t for m in map_markers):
        return "map"
    if any(m in t for m in policy_markers):
        return "policy"

    # If it looks like there are exhibits/attachments but we can't classify.
    if re.search(r"(?i)\b(exhibit|attachment)\b", text):
        return "exhibit"
    return None


def extract_attachments(text: str, *, agenda_end: int = 0) -> List[Attachment]:
    """Best-effort extraction of attachments/exhibits from packet text.

    Strategy:
    - Find common attachment/exhibit headings.
    - Segment body text by heading-to-heading spans.
    - If no headings are found but the text beyond agenda_end looks attachment-like,
      create a single bucket.

    agenda_end is a hint for where agenda content likely ends.
    """

    if agenda_end < 0:
        agenda_end = 0
    agenda_end = min(agenda_end, len(text))

    # Primary heading forms.
    # Examples:
    #   ATTACHMENT 1: Staff Report
    #   Exhibit A - Plat
    rx_primary = re.compile(
        r"(?m)^\s*(?P<kind>ATTACHMENT|EXHIBIT)\s+(?P<id>[A-Z]|\d{1,3})\b\s*[:\-\.]?\s*(?P<title>[^\n]{0,120})$",
        re.IGNORECASE,
    )

    # Secondary headings commonly used in packets.
    rx_secondary = re.compile(
        r"(?m)^\s*(?P<title>(STAFF\s+REPORT|VICINITY\s+MAP|ZONING\s+MAP|PLAT|MAP|POLICY)[^\n]{0,120})$",
        re.IGNORECASE,
    )

    headings: List[tuple[int, int, str, str, Optional[str]]] = []
    # (start, end, attachment_id, title, type_guess)

    for m in rx_primary.finditer(text):
        start = m.start()
        if start < agenda_end - 500:
            # If it's well before the agenda cutoff, it's probably part of the agenda list.
            continue
        kind = _clean_line(m.group("kind")).upper()
        ident = _clean_line(m.group("id")).upper()
        title_part = _clean_line(m.group("title") or "")
        title = f"{kind} {ident}" + (f": {title_part}" if title_part else "")
        attachment_id = f"{kind}_{ident}"
        headings.append((start, m.end(), attachment_id, title, guess_attachment_type(title)))

    for m in rx_secondary.finditer(text):
        start = m.start()
        if start < agenda_end:
            continue
        raw_title = _clean_line(m.group("title"))
        # Avoid very generic lines that happen constantly.
        if len(raw_title) < 4:
            continue
        # Secondary headings are more error-prone; require them to look like headings.
        letters = [c for c in raw_title if c.isalpha()]
        if letters:
            upper = sum(1 for c in letters if c.isupper())
            is_all_capsish = upper >= len(letters) * 0.7
        else:
            is_all_capsish = False
        if not is_all_capsish and " - " not in raw_title:
            continue

        # Make a stable synthetic id.
        norm = re.sub(r"[^a-z0-9]+", "_", raw_title.casefold()).strip("_")
        attachment_id = f"HEADING_{norm[:40] or 'attachment'}"
        headings.append((start, m.end(), attachment_id, raw_title, guess_attachment_type(raw_title)))

    headings.sort(key=lambda x: x[0])

    attachments: List[Attachment] = []
    for idx, (start, end, attachment_id, title, type_guess) in enumerate(headings):
        next_start = headings[idx + 1][0] if idx + 1 < len(headings) else len(text)
        body = text[end:next_start].strip("\n ")

        if len(body) > 40_000:
            body = body[:40_000].rstrip() + "\n[...truncated...]"

        combined_for_guess = f"{title}\n{body[:4000]}"
        guessed = guess_attachment_type(combined_for_guess) or type_guess

        attachments.append(
            Attachment(
                start=start,
                end=next_start,
                attachment_id=attachment_id,
                title=title,
                type_guess=guessed,
                body_text=body,
            )
        )

    if attachments:
        return attachments

    # Fallback: create a single bucket if the tail looks attachment-like.
    tail = text[agenda_end: min(len(text), agenda_end + 20_000)]
    if guess_attachment_type(tail) is None and not re.search(r"(?i)\b(exhibit|attachment|plat|staff report|map|policy)\b", tail):
        return []

    body = text[agenda_end:].strip("\n ")
    if len(body) > 40_000:
        body = body[:40_000].rstrip() + "\n[...truncated...]"

    return [
        Attachment(
            start=agenda_end,
            end=len(text),
            attachment_id="ATTACHMENTS",
            title="Attachments / Exhibits (auto)",
            type_guess=guess_attachment_type(body[:8000]),
            body_text=body,
        )
    ]
