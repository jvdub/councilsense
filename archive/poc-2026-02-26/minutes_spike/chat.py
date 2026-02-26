from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class EvidencePointer:
    bucket: str  # agenda_item | attachment | meeting_text
    source: str
    start: Optional[int]
    end: Optional[int]
    snippet: str
    agenda_item: Optional[Dict[str, str]] = None
    attachment: Optional[Dict[str, Any]] = None


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _snippet_around(text: str, *, start: int, end: int, window: int = 180) -> str:
    if start < 0:
        start = 0
    if end < start:
        end = start
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    snip = text[lo:hi]
    snip = _collapse_ws(snip)
    if lo > 0:
        snip = "..." + snip
    if hi < len(text):
        snip = snip + "..."
    return snip


def _find_first_match(text: str, needle: str) -> Optional[Tuple[int, int]]:
    if not text or not needle:
        return None
    m = re.search(re.escape(needle), text, flags=re.IGNORECASE)
    if not m:
        return None
    return (m.start(), m.end())


def _find_first_any_match(text: str, needles: List[str]) -> Optional[Tuple[int, int, str]]:
    for n in needles:
        n = (n or "").strip()
        if not n:
            continue
        m = _find_first_match(text, n)
        if m:
            return (m[0], m[1], n)
    return None


_WHY_MENTIONED_RE = re.compile(r"(?i)\bwhy\s+was\s+(?P<what>.+?)\s+mentioned\b")

_TOPIC_RE = re.compile(
    r"(?is)\b(?:what\s+happened\s+(?:related\s+to|about)|related\s+to|about)\s+(?P<what>.+?)\s*[?.!]*$"
)

_DECIDED_ABOUT_RE = re.compile(r"(?is)\bwhat\s+was\s+decided\s+about\s+(?P<what>.+?)\s*[?.!]*$")

_ORDINANCE_Q_RE = re.compile(r"(?i)\b(ordinance|ordinances|resolution|resolutions)\b")

_ORDINANCE_HINTS_RE = re.compile(
    r"(?i)\b(ordinance|resolution|public hearing|code|chapter|section|amend|amended|change|changed|update|updated|modify|modified|repeal|repealed|adopt|adopted)\b"
)

_DECISION_VERBS_RE = re.compile(
    r"(?i)\b(approved|denied|adopted|passed|failed|tabled|continued|motion|moved|seconded|vote|voted|unanimous|carried|decision|decided)\b"
)


def _extract_target_phrase(question: str) -> Optional[str]:
    q = (question or "").strip()
    if not q:
        return None

    m = _WHY_MENTIONED_RE.search(q)
    if m:
        what = (m.group("what") or "").strip().strip("\"'“”‘’.?!")
        if what:
            # If the user asked a long clause, keep it bounded.
            if len(what) > 120:
                what = what[:120].rstrip() + "..."
            return what

    # Fallback: if the user mentions a quoted phrase, use the first quoted segment.
    qm = re.search(r"[\"“](.+?)[\"”]", q)
    if qm:
        what = (qm.group(1) or "").strip()
        return what or None

    # Another fallback: if a known interest term is present.
    if "sunset flats" in q.casefold():
        return "Sunset Flats"

    return None


def _extract_topic(question: str) -> Optional[str]:
    q = (question or "").strip()
    if not q:
        return None

    m = _DECIDED_ABOUT_RE.search(q)
    if m:
        what = (m.group("what") or "").strip().strip("\"'“”‘’.?!")
        return what or None

    m = _TOPIC_RE.search(q)
    if m:
        what = (m.group("what") or "").strip().strip("\"'“”‘’.?!")
        return what or None

    # Heuristic fallbacks for common interests.
    q_cf = q.casefold()
    if "sunset flats" in q_cf:
        return "Sunset Flats"
    if "laundromat" in q_cf or "laundromats" in q_cf:
        return "laundromat"

    return None


def _topic_variants(topic: str) -> List[str]:
    t = (topic or "").strip()
    if not t:
        return []
    variants = [t]
    tl = t.casefold()
    if tl.endswith("s") and len(t) > 3:
        variants.append(t[:-1])
    if not tl.endswith("s"):
        variants.append(t + "s")
    # De-dupe while preserving order.
    out: List[str] = []
    seen = set()
    for v in variants:
        key = v.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _best_effort_decision_snippet(text: str, *, topic_match: Tuple[int, int]) -> str:
    start, end = topic_match
    # If a decision verb appears near the topic, use that as the anchor.
    window = 600
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    region = text[lo:hi]
    m = _DECISION_VERBS_RE.search(region)
    if m:
        ds = lo + m.start()
        de = lo + m.end()
        return _snippet_around(text, start=ds, end=de)
    return _snippet_around(text, start=start, end=end)


def _collect_evidence_for_topic(
    *,
    topic: str,
    agenda_items: List[Dict[str, Any]],
    attachments: List[Dict[str, Any]],
    meeting_text: str,
    max_snippets: int = 3,
) -> List[EvidencePointer]:
    needles = _topic_variants(topic)
    evidence: List[EvidencePointer] = []

    # Attachments first (matches G1 behavior and is often where project names appear).
    for att in attachments:
        title = str(att.get("title") or "")
        body = str(att.get("body_text") or "")
        combined = f"{title}\n\n{body}".strip()
        m = _find_first_any_match(combined, needles)
        if not m:
            continue
        start, end, _ = m
        snippet = _best_effort_decision_snippet(combined, topic_match=(start, end))
        evidence.append(
            EvidencePointer(
                bucket="attachment",
                source="attachment",
                start=start,
                end=end,
                snippet=snippet,
                attachment={
                    "attachment_id": str(att.get("attachment_id") or ""),
                    "title": title,
                    "type_guess": att.get("type_guess"),
                },
            )
        )
        if len(evidence) >= max_snippets:
            return evidence

    for item in agenda_items:
        item_id = str(item.get("item_id") or "")
        title = str(item.get("title") or "")
        body = str(item.get("body_text") or "")
        combined = f"{title}\n\n{body}".strip()
        m = _find_first_any_match(combined, needles)
        if not m:
            continue
        start, end, _ = m
        snippet = _best_effort_decision_snippet(combined, topic_match=(start, end))
        evidence.append(
            EvidencePointer(
                bucket="agenda_item",
                source="agenda_item",
                start=start,
                end=end,
                snippet=snippet,
                agenda_item={"item_id": item_id, "title": title},
            )
        )
        if len(evidence) >= max_snippets:
            return evidence

    if meeting_text:
        m2 = _find_first_any_match(meeting_text, needles)
        if m2:
            start, end, _ = m2
            evidence.append(
                EvidencePointer(
                    bucket="meeting_text",
                    source="meeting_text",
                    start=start,
                    end=end,
                    snippet=_best_effort_decision_snippet(meeting_text, topic_match=(start, end)),
                )
            )

    return evidence


def _collect_evidence_for_ordinances(
    *,
    agenda_items: List[Dict[str, Any]],
    attachments: List[Dict[str, Any]],
    max_snippets: int = 3,
) -> Tuple[List[str], List[EvidencePointer]]:
    """Return (summaries, evidence) for ordinance/resolution-like items."""

    summaries: List[str] = []
    evidence: List[EvidencePointer] = []

    def consider_agenda_item(item: Dict[str, Any]) -> None:
        nonlocal summaries, evidence
        item_id = str(item.get("item_id") or "")
        title = str(item.get("title") or "")
        body = str(item.get("body_text") or "")
        combined = f"{title}\n\n{body}".strip()
        if not _ORDINANCE_HINTS_RE.search(combined):
            return
        label = (f"{item_id} — {title}" if item_id and title else (title or item_id or "(agenda item)"))
        summaries.append(label)
        if len(evidence) < max_snippets:
            m = _ORDINANCE_HINTS_RE.search(combined)
            if m:
                snippet = _snippet_around(combined, start=m.start(), end=m.end())
            else:
                snippet = _snippet_around(combined, start=0, end=min(40, len(combined)))
            evidence.append(
                EvidencePointer(
                    bucket="agenda_item",
                    source="agenda_item",
                    start=m.start() if m else None,
                    end=m.end() if m else None,
                    snippet=snippet,
                    agenda_item={"item_id": item_id, "title": title},
                )
            )

    # Prefer agenda items; ordinances are usually on the agenda.
    for item in agenda_items:
        consider_agenda_item(item)

    # If we found none, fall back to attachments (some packets shove these into exhibits).
    if not summaries:
        for att in attachments:
            title = str(att.get("title") or "")
            body = str(att.get("body_text") or "")
            combined = f"{title}\n\n{body}".strip()
            if not _ORDINANCE_HINTS_RE.search(combined):
                continue
            label = title or str(att.get("attachment_id") or "(attachment)")
            summaries.append(label)
            if len(evidence) < max_snippets:
                m = _ORDINANCE_HINTS_RE.search(combined)
                snippet = _snippet_around(combined, start=m.start(), end=m.end()) if m else _snippet_around(combined, start=0, end=min(40, len(combined)))
                evidence.append(
                    EvidencePointer(
                        bucket="attachment",
                        source="attachment",
                        start=m.start() if m else None,
                        end=m.end() if m else None,
                        snippet=snippet,
                        attachment={
                            "attachment_id": str(att.get("attachment_id") or ""),
                            "title": title,
                            "type_guess": att.get("type_guess"),
                        },
                    )
                )

    return summaries, evidence


def _load_meeting_artifacts(*, meeting_dir: Path) -> Dict[str, Any]:
    agenda_items: List[Dict[str, Any]] = []
    attachments: List[Dict[str, Any]] = []

    agenda_path = meeting_dir / "agenda_items.json"
    if agenda_path.exists():
        try:
            obj = _load_json(agenda_path)
            if isinstance(obj, list):
                agenda_items = [x for x in obj if isinstance(x, dict)]
        except Exception:
            agenda_items = []

    attachments_path = meeting_dir / "attachments.json"
    if attachments_path.exists():
        try:
            obj = _load_json(attachments_path)
            if isinstance(obj, list):
                attachments = [x for x in obj if isinstance(x, dict)]
        except Exception:
            attachments = []

    # Prefer stored extracted text from import (deterministic).
    meeting_text = ""
    for fn in ("extracted_text.txt", "extracted_text_from_txt.txt"):
        p = meeting_dir / fn
        if p.exists():
            meeting_text = p.read_text(encoding="utf-8", errors="replace")
            break

    return {
        "agenda_items": agenda_items,
        "attachments": attachments,
        "meeting_text": meeting_text,
    }


def answer_question(*, store_dir: Path, meeting_id: str, question: str) -> Dict[str, Any]:
    """Answer a question scoped to a single meeting.

    This is a deterministic, evidence-first helper suitable for the MVP spike.

    Returns a JSON-serializable dict:
      {meeting_id, question, answer, found, evidence[]}

    Evidence entries include a source pointer (agenda item / attachment) when possible.
    """

    store_dir = store_dir.resolve()
    meeting_dir = (store_dir / meeting_id).resolve()
    if not meeting_dir.exists():
        raise FileNotFoundError(f"Meeting folder not found: {meeting_dir}")

    artifacts = _load_meeting_artifacts(meeting_dir=meeting_dir)
    agenda_items = artifacts["agenda_items"]
    attachments = artifacts["attachments"]
    meeting_text = str(artifacts.get("meeting_text") or "")

    # --- G1: Why-was-X-mentioned? ---
    target = _extract_target_phrase(question)
    if target:
        evidence = _collect_evidence_for_topic(
            topic=target,
            agenda_items=agenda_items,
            attachments=attachments,
            meeting_text=meeting_text,
            max_snippets=3,
        )
        if not evidence:
            return {
                "meeting_id": meeting_id,
                "question": question,
                "found": False,
                "answer": f"Not found: I couldn't find evidence for '{target}' in this meeting.",
                "evidence": [],
            }

        first = evidence[0]
        if first.bucket == "attachment" and first.attachment:
            where = first.attachment.get("title") or "an attachment"
            answer = f"Found evidence in {where}."
        elif first.bucket == "agenda_item" and first.agenda_item:
            where = first.agenda_item.get("item_id") or "an agenda item"
            answer = f"Found evidence in agenda item {where}."
        else:
            answer = "Found evidence in the meeting text."

        return {
            "meeting_id": meeting_id,
            "question": question,
            "found": True,
            "answer": answer,
            "evidence": [e.__dict__ for e in evidence],
        }

    # --- G2: Ordinances/resolutions ---
    if _ORDINANCE_Q_RE.search(question or ""):
        summaries, evidence = _collect_evidence_for_ordinances(agenda_items=agenda_items, attachments=attachments, max_snippets=3)
        if not summaries:
            return {
                "meeting_id": meeting_id,
                "question": question,
                "found": False,
                "answer": "Not found: I couldn't find any ordinance/resolution items in this meeting.",
                "evidence": [],
            }

        # Keep the answer single-line for the minimal UI.
        head = summaries[:4]
        suffix = "" if len(summaries) <= 4 else f" (+{len(summaries) - 4} more)"
        answer = "Ordinances/resolutions found: " + "; ".join(head) + suffix
        return {
            "meeting_id": meeting_id,
            "question": question,
            "found": True,
            "answer": answer,
            "evidence": [e.__dict__ for e in evidence],
        }

    # --- G2: General topic / decided-about / related-to ---
    topic = _extract_topic(question)
    if topic:
        evidence = _collect_evidence_for_topic(
            topic=topic,
            agenda_items=agenda_items,
            attachments=attachments,
            meeting_text=meeting_text,
            max_snippets=3,
        )
        if not evidence:
            return {
                "meeting_id": meeting_id,
                "question": question,
                "found": False,
                "answer": f"Not found: I couldn't find evidence for '{topic}' in this meeting.",
                "evidence": [],
            }

        first = evidence[0]
        if first.bucket == "attachment" and first.attachment:
            where = first.attachment.get("title") or "an attachment"
            answer = f"Found '{topic}' in {where}."
        elif first.bucket == "agenda_item" and first.agenda_item:
            where = first.agenda_item.get("item_id") or "an agenda item"
            answer = f"Found '{topic}' in agenda item {where}."
        else:
            answer = f"Found '{topic}' in the meeting text."

        return {
            "meeting_id": meeting_id,
            "question": question,
            "found": True,
            "answer": answer,
            "evidence": [e.__dict__ for e in evidence],
        }

    return {
        "meeting_id": meeting_id,
        "question": question,
        "found": False,
        "answer": "Not found: I couldn't tell what to search for in that question.",
        "evidence": [],
    }
