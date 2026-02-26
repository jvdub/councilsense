from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .agenda import AgendaItem, extract_agenda_items
from .attachments import Attachment, extract_attachments
from .extract import PdfExtractionError, extract_pdf_text_canonical, read_text_file
from .profile import ProfileError, init_profile, load_profile, resolve_profile_path
from .llm import LLMError, ProviderConfig, create_llm_provider
from .db import DB_FILENAME, get_llm_cache, put_llm_cache, stable_hash_json
from .prompts import (
    SEMANTIC_CLASSIFY_RELEVANCE,
    SUMMARIZE_AGENDA_ITEM_BULLETS,
    SUMMARIZE_AGENDA_ITEM_TOON,
    build_semantic_relevance_prompt,
    build_summarize_agenda_item_toon_prompt,
)
from .toon import ToonDecodeError, decode_toon_to_json, encode_json_to_toon
from .store import IngestionError, generate_meeting_id, import_meeting


@dataclass(frozen=True)
class Evidence:
    source: str
    start: int
    end: int
    snippet: str


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "will",
}


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fallback_citation(body_text: str, *, max_chars: int = 240) -> str:
    # Try to pick a meaningful sentence/line.
    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
    for ln in lines:
        ln = _collapse_ws(ln)
        if len(ln) >= 40:
            return ln[:max_chars]
    compact = _collapse_ws(body_text)
    return compact[:max_chars] if compact else ""


def _extract_actions_simple(title: str, body_text: str, *, max_items: int = 6) -> List[str]:
    t = (title or "") + "\n" + (body_text or "")
    t_low = t.lower()
    actions: List[str] = []

    def add(val: str) -> None:
        val = val.strip()
        if val and val not in actions:
            actions.append(val)

    if "ordinance" in t_low or "public hearing" in t_low:
        add("Ordinance / public hearing item")
    if "resolution" in t_low:
        add("Resolution considered")
    if re.search(r"\b(motion|moved)\b", t_low):
        add("Motion discussed")
    if re.search(r"\b(vote|voted|unanimous)\b", t_low):
        add("Vote recorded")
    if re.search(r"\b(approve|approval|adopt|adoption|authorize|authorization)\b", t_low):
        add("Approval/adoption requested")
    if re.search(r"\b(deny|denial)\b", t_low):
        add("Denial discussed")

    return actions[:max_items]


_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")


def _extract_entities_simple(text: str, *, max_items: int = 12) -> List[str]:
    if not text:
        return []
    candidates = _ENTITY_RE.findall(text)
    out: List[str] = []
    seen = set()
    for c in candidates:
        c = c.strip()
        if not c or len(c) < 3:
            continue
        low = c.lower()
        if low in ("city council", "council", "mayor", "staff"):
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(c)
        if len(out) >= max_items:
            break
    return out


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


def _extract_key_terms_simple(title: str, body_text: str, *, max_items: int = 10) -> List[str]:
    text = f"{title}\n{body_text}".strip()
    if not text:
        return []
    counts: Dict[str, int] = {}
    for w in _WORD_RE.findall(text):
        w_low = w.lower()
        if w_low in _STOPWORDS:
            continue
        if len(w_low) <= 3:
            continue
        counts[w_low] = counts.get(w_low, 0) + 1

    # Prefer higher counts then alphabetical for stability.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for (w, _c) in ranked[:max_items]]


def _normalize_str_list(val: Any) -> List[str]:
    if not isinstance(val, list):
        return []
    out: List[str] = []
    for item in val:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _ensure_evidence_citation(body_text: str, citations: List[str]) -> List[str]:
    # Ensure at least one evidence quote/snippet is present.
    cits = [c.strip() for c in citations if isinstance(c, str) and c.strip()]
    if cits:
        return cits
    fallback = _fallback_citation(body_text)
    return [fallback] if fallback else []


def _confidence_from_hits(*, rule_type: str, hits: int, min_hits: int) -> float:
    if hits <= 0:
        return 0.0
    base = 0.45
    if rule_type == "keyword_with_context":
        base = 0.55
    # Scale gently with hits; cap < 1.0 to reflect heuristic uncertainty.
    scaled = base + min(0.35, 0.10 * max(0, hits - min_hits))
    return float(min(0.95, max(base, scaled)))


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from model output."""

    if not isinstance(text, str) or not text.strip():
        return None

    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(s[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _normalize_confidence(val: object) -> float:
    try:
        f = float(val)  # type: ignore[arg-type]
    except Exception:
        return 0.0
    if f != f:
        return 0.0
    return float(max(0.0, min(1.0, f)))


def _semantic_classify_relevance(
    *,
    llm: "llm.LLMProvider",
    db_path: Optional[Path],
    provider: str,
    endpoint: str,
    model: str,
    timeout_s: float,
    generated_at: str,
    category_id: str,
    category_description: str,
    category_keywords: List[str],
    candidate_kind: str,
    candidate_title: str,
    candidate_text: str,
    evidence_snippets: List[str],
) -> Dict[str, Any]:
    prompt_template = SEMANTIC_CLASSIFY_RELEVANCE

    prompt = build_semantic_relevance_prompt(
        category_id=category_id,
        category_description=category_description,
        category_keywords=category_keywords,
        candidate_kind=candidate_kind,
        candidate_title=candidate_title,
        candidate_text=candidate_text,
        evidence_snippets=evidence_snippets,
    )

    cache_key: Optional[str] = None
    cache_hit = False
    cached_obj: Optional[object] = None
    if db_path is not None:
        cache_input = {
            "kind": "pass_b.semantic_relevance",
            "category_id": category_id,
            "category_description": category_description,
            "category_keywords": category_keywords,
            "candidate_kind": candidate_kind,
            "candidate_title": candidate_title,
            "candidate_text": candidate_text,
            "evidence_snippets": evidence_snippets,
            "prompt_id": prompt_template.id,
            "prompt_version": int(prompt_template.version),
            "model": {
                "provider": str(provider),
                "endpoint": str(endpoint),
                "model": str(model).strip(),
            },
        }
        cache_key = stable_hash_json(cache_input)
        cached_obj = get_llm_cache(db_path=db_path, cache_key=cache_key)

    raw_text: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None

    if isinstance(cached_obj, dict) and isinstance(cached_obj.get("result"), dict):
        parsed = cached_obj.get("result")
        cache_hit = True
    else:
        raw_text = llm.generate_text(prompt=prompt)
        parsed = _extract_first_json_object(raw_text)
        if db_path is not None and cache_key is not None:
            try:
                put_llm_cache(
                    db_path=db_path,
                    cache_key=cache_key,
                    kind="pass_b.semantic_relevance",
                    obj={"result": parsed, "raw_text": raw_text},
                    model_provider=str(provider),
                    model_endpoint=str(endpoint),
                    model=str(model).strip(),
                    prompt_id=prompt_template.id,
                    prompt_version=int(prompt_template.version),
                )
            except Exception:
                pass

    relevant = bool(parsed.get("relevant")) if isinstance(parsed, dict) else False
    confidence = _normalize_confidence(parsed.get("confidence")) if isinstance(parsed, dict) else (0.6 if relevant else 0.0)
    why = parsed.get("why") if isinstance(parsed, dict) else None
    if not isinstance(why, str) or not why.strip():
        why = "Semantically relevant" if relevant else "Not semantically relevant"

    ev_list = parsed.get("evidence") if isinstance(parsed, dict) else []
    quotes: List[str] = []
    if isinstance(ev_list, list):
        for q in ev_list:
            if isinstance(q, str) and q.strip():
                quotes.append(q.strip())
            if len(quotes) >= 3:
                break

    return {
        "relevant": relevant,
        "confidence": confidence,
        "why": why,
        "evidence_quotes": quotes,
        "provenance": {
            "generated_at": generated_at,
            "llm": {
                "provider": str(provider),
                "endpoint": str(endpoint),
                "model": str(model).strip(),
                "timeout_s": float(timeout_s),
            },
            "prompt_template": {
                "id": prompt_template.id,
                "version": int(prompt_template.version),
            },
            "cache": {"hit": bool(cache_hit), "key": cache_key},
        },
    }


def _pass_b_for_agenda_item(
    *,
    item: Dict[str, Any],
    rules: List[Dict[str, Any]],
    evidence_cfg: Dict[str, Any],
    semantic_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Compute Pass B relevance classification for one agenda item.

    Returns (per_rule_results, highlights_for_item).
    """

    item_id = str(item.get("item_id") or "")
    title = str(item.get("title") or "")
    body_text = str(item.get("body_text") or "")
    combined_text = f"{title}\n\n{body_text}".strip()

    per_rule: Dict[str, Any] = {}
    highlights: List[Dict[str, Any]] = []

    for rule in rules:
        rule_id = str(rule.get("id") or "")
        if not rule_id:
            continue
        rr = evaluate_rule(rule, {"agenda_item": combined_text}, evidence_cfg)
        hits = int(rr.get("hits", 0) or 0)
        min_hits = int(rr.get("min_hits", 1) or 1)
        rule_type = str(rr.get("type") or "")
        relevant = bool(rr.get("alert"))

        evidence = rr.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        # Attach explicit agenda item pointers to evidence.
        normalized_evidence: List[Dict[str, Any]] = []
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            normalized_evidence.append(
                {
                    "bucket": "agenda_item",
                    "agenda_item": {"item_id": item_id, "title": title},
                    "source": "agenda_item",
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "snippet": ev.get("snippet"),
                }
            )

        # If relevant but evidence is missing, synthesize a conservative snippet.
        if relevant and not normalized_evidence:
            snippet = _fallback_citation(combined_text)
            if snippet:
                normalized_evidence = [
                    {
                        "bucket": "agenda_item",
                        "agenda_item": {"item_id": item_id, "title": title},
                        "source": "agenda_item",
                        "start": None,
                        "end": None,
                        "snippet": snippet,
                    }
                ]

        # Guardrail: don't produce an explanation if we have no evidence.
        why = None
        if relevant and normalized_evidence:
            desc = rule.get("description")
            if isinstance(desc, str) and desc.strip():
                why = f"Matched interest rule: {desc.strip()}"
            else:
                why = f"Matched interest rule: {rule_id}"

        confidence = _confidence_from_hits(rule_type=rule_type, hits=hits, min_hits=min_hits) if relevant else 0.0

        semantic = None
        if isinstance(semantic_overrides, dict):
            semantic = semantic_overrides.get(rule_id)
        if isinstance(semantic, dict) and "relevant" in semantic:
            # Apply semantic filter/override.
            relevant = bool(semantic.get("relevant"))
            why = semantic.get("why") if isinstance(semantic.get("why"), str) else why
            confidence = _normalize_confidence(semantic.get("confidence"))
            quotes = semantic.get("evidence_quotes")
            if isinstance(quotes, list) and quotes:
                normalized_evidence = [
                    {
                        "bucket": "agenda_item",
                        "agenda_item": {"item_id": item_id, "title": title},
                        "source": "agenda_item",
                        "start": None,
                        "end": None,
                        "snippet": q,
                    }
                    for q in quotes
                    if isinstance(q, str) and q.strip()
                ][:3]
            per_rule[rule_id] = {
                "relevant": relevant,
                "why": why,
                "confidence": confidence,
                "hits": hits,
                "evidence": normalized_evidence,
                "semantic": semantic,
            }
        else:
            per_rule[rule_id] = {
                "relevant": relevant,
                "why": why,
                "confidence": confidence,
                "hits": hits,
                "evidence": normalized_evidence,
            }

        if relevant and normalized_evidence:
            highlights.append(
                {
                    "title": f"{item_id}: {title}" if item_id else title,
                    "category": rule_id,
                    "rule_id": rule_id,
                    "why": why,
                    "confidence": confidence,
                    "evidence": normalized_evidence[:3],
                    "links": {"agenda_item": {"item_id": item_id, "title": title}},
                }
            )

    return per_rule, highlights


def _attachment_highlights_from_rule_results(
    *,
    rule_results: List[Dict[str, Any]],
    existing_highlights: List[Dict[str, Any]],
    semantic_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build highlights sourced from attachments/exhibits.

    E1 acceptance: highlights can be backed by either agenda items or attachments,
    but must include 1–3 evidence snippets with source pointers.

    This derives attachment highlights from the full-document rule results, which
    already have attachment bucketing applied via `_rule_explanation`.
    """

    existing_rule_ids: set[str] = set()
    for h in existing_highlights:
        if isinstance(h, dict):
            rid = h.get("rule_id")
            if isinstance(rid, str) and rid:
                existing_rule_ids.add(rid)

    seen: set[tuple[str, str]] = set()  # (rule_id, attachment_id)
    out: List[Dict[str, Any]] = []

    for rr in rule_results:
        if not isinstance(rr, dict) or not rr.get("alert"):
            continue

        rule_id = rr.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            continue

        # Prefer agenda-item highlights when they exist; only add attachment
        # highlights when the rule's refs point to attachments (no agenda refs).
        agenda_refs = rr.get("agenda_refs")
        attachment_refs = rr.get("attachment_refs")
        has_agenda_refs = isinstance(agenda_refs, list) and len(agenda_refs) > 0
        has_attachment_refs = isinstance(attachment_refs, list) and len(attachment_refs) > 0
        if rule_id in existing_rule_ids and has_agenda_refs:
            continue
        if not has_attachment_refs:
            continue

        evidence = rr.get("evidence") or []
        if not isinstance(evidence, list) or not evidence:
            continue

        # Group evidence by attachment_id.
        by_attachment: Dict[str, List[Dict[str, Any]]] = {}
        attachment_meta: Dict[str, Dict[str, Any]] = {}
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            if ev.get("bucket") != "attachment":
                continue
            att = ev.get("attachment")
            if not isinstance(att, dict):
                continue
            attachment_id = att.get("attachment_id")
            title = att.get("title")
            if not isinstance(attachment_id, str) or not attachment_id:
                continue
            if not isinstance(title, str) or not title:
                continue

            by_attachment.setdefault(attachment_id, []).append(ev)
            attachment_meta[attachment_id] = {
                "attachment_id": attachment_id,
                "title": title,
                "type_guess": att.get("type_guess") if isinstance(att.get("type_guess"), str) else None,
            }

        if not by_attachment:
            continue

        hits = int(rr.get("hits", 0) or 0)
        min_hits = int(rr.get("min_hits", 1) or 1)
        rule_type = str(rr.get("type") or "")
        confidence = _confidence_from_hits(rule_type=rule_type, hits=hits, min_hits=min_hits)

        why = rr.get("explanation")
        if not isinstance(why, str) or not why.strip():
            desc = rr.get("description")
            if isinstance(desc, str) and desc.strip():
                why = f"Matched interest rule: {desc.strip()}"
            else:
                why = f"Matched interest rule: {rule_id}"

        for attachment_id, evs in by_attachment.items():
            sem = None
            if isinstance(semantic_overrides, dict):
                sem_by_rule = semantic_overrides.get(rule_id)
                if isinstance(sem_by_rule, dict):
                    sem = sem_by_rule.get(attachment_id)
            if isinstance(sem, dict) and "relevant" in sem and not bool(sem.get("relevant")):
                continue

            key = (rule_id, attachment_id)
            if key in seen:
                continue
            seen.add(key)

            meta = attachment_meta.get(attachment_id) or {"attachment_id": attachment_id, "title": attachment_id}

            # Keep at most 3 evidence snippets; dedupe by source/start/end.
            normalized: List[Dict[str, Any]] = []
            dedupe_local: set[tuple[Any, Any, Any, Any]] = set()
            for ev in evs:
                k = (ev.get("source"), ev.get("start"), ev.get("end"), ev.get("snippet"))
                if k in dedupe_local:
                    continue
                dedupe_local.add(k)
                normalized.append(
                    {
                        "bucket": "attachment",
                        "attachment": {
                            "attachment_id": meta.get("attachment_id"),
                            "title": meta.get("title"),
                            "type_guess": meta.get("type_guess"),
                        },
                        "source": ev.get("source"),
                        "start": ev.get("start"),
                        "end": ev.get("end"),
                        "snippet": ev.get("snippet"),
                    }
                )
                if len(normalized) >= 3:
                    break

            if isinstance(sem, dict) and bool(sem.get("relevant")):
                why = sem.get("why") if isinstance(sem.get("why"), str) else why
                confidence = _normalize_confidence(sem.get("confidence"))
                quotes = sem.get("evidence_quotes")
                if isinstance(quotes, list) and quotes:
                    normalized = [
                        {
                            "bucket": "attachment",
                            "attachment": {
                                "attachment_id": meta.get("attachment_id"),
                                "title": meta.get("title"),
                                "type_guess": meta.get("type_guess"),
                            },
                            "source": "attachment",
                            "start": None,
                            "end": None,
                            "snippet": q,
                        }
                        for q in quotes
                        if isinstance(q, str) and q.strip()
                    ][:3]

            if not normalized:
                continue

            out.append(
                {
                    "title": f"{meta.get('attachment_id')}: {meta.get('title')}",
                    "category": rule_id,
                    "rule_id": rule_id,
                    "why": why,
                    "confidence": confidence,
                    "evidence": normalized,
                    "semantic": sem if isinstance(sem, dict) else None,
                    "links": {"attachment": meta},
                }
            )

    return out


def _pick_evidence_snippets(obj: Dict[str, Any], *, max_snips: int = 2) -> List[Dict[str, Any]]:
    """Try to extract evidence snippets from an agenda item dict."""
    out: List[Dict[str, Any]] = []
    pass_a = obj.get("pass_a") or {}
    if isinstance(pass_a, dict):
        citations = pass_a.get("citations")
        if isinstance(citations, list):
            for c in citations:
                if isinstance(c, str) and c.strip():
                    out.append({"source": "agenda_item", "snippet": c.strip()})
                    if len(out) >= max_snips:
                        return out

    body_text = str(obj.get("body_text") or "")
    if body_text.strip():
        fallback = _fallback_citation(body_text)
        if fallback:
            out.append({"source": "agenda_item", "snippet": fallback})

    return out[:max_snips]


def _meeting_pass_c(
    *,
    meeting_id: str,
    agenda_items_full: List[Dict[str, Any]],
    things_you_care_about: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a small meeting-level summary from existing outputs.

    D3 acceptance:
    - top 3–7 highlights
    - any important ordinances/resolutions
    - watchlist hits section
    Evidence-first: every highlight must include evidence snippets.
    """

    highlights: List[Dict[str, Any]] = []

    # 1) Prefer existing "things_you_care_about" (already evidence-backed).
    for h in things_you_care_about:
        if not isinstance(h, dict):
            continue
        ev = h.get("evidence")
        if isinstance(ev, list) and ev:
            highlights.append(h)
        if len(highlights) >= 7:
            break

    # 2) Fill remaining highlights with per-agenda-item summaries + citations.
    if len(highlights) < 3:
        for item in agenda_items_full:
            if len(highlights) >= 3:
                break
            item_id = str(item.get("item_id") or "")
            title = str(item.get("title") or "")
            bullets = []
            pass_a = item.get("pass_a")
            if isinstance(pass_a, dict):
                bullets = _normalize_str_list(pass_a.get("summary"))
            if not bullets:
                continue
            ev = _pick_evidence_snippets(item)
            if not ev:
                continue
            highlights.append(
                {
                    "title": f"{item_id}: {title}" if item_id else title,
                    "category": "meeting_highlight",
                    "why": bullets[0],
                    "confidence": 0.5,
                    "evidence": [
                        {
                            "bucket": "agenda_item",
                            "agenda_item": {"item_id": item_id, "title": title},
                            "snippet": ev[0].get("snippet"),
                        }
                    ],
                    "links": {"agenda_item": {"item_id": item_id, "title": title}},
                }
            )

    # Ordinances/resolutions list (best-effort keyword scan).
    ordinances: List[Dict[str, Any]] = []
    for item in agenda_items_full:
        item_id = str(item.get("item_id") or "")
        title = str(item.get("title") or "")
        t_low = title.lower()
        if "ordinance" not in t_low and "resolution" not in t_low:
            continue
        ev = _pick_evidence_snippets(item)
        if not ev:
            continue
        kind = "ordinance" if "ordinance" in t_low else "resolution"
        ordinances.append(
            {
                "kind": kind,
                "item_id": item_id,
                "title": title,
                "evidence": [
                    {
                        "bucket": "agenda_item",
                        "agenda_item": {"item_id": item_id, "title": title},
                        "snippet": ev[0].get("snippet"),
                    }
                ],
            }
        )

    # Watchlist hits: summarize how many highlights per category.
    counts: Dict[str, int] = {}
    for h in things_you_care_about:
        if not isinstance(h, dict):
            continue
        cat = h.get("category")
        if isinstance(cat, str) and cat:
            counts[cat] = counts.get(cat, 0) + 1
    watchlist_hits = [{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {
        "meeting_id": meeting_id,
        "highlights": highlights[:7],
        "ordinances_resolutions": ordinances[:20],
        "watchlist_hits": watchlist_hits,
    }


def _lower(text: str) -> str:
    return text.casefold()


def _find_keyword_hits(text: str, keyword: str) -> List[Tuple[int, int]]:
    # Simple substring search with overlapping support.
    # Uses casefolded text for matching; indices refer to original normalized text.
    lowered = _lower(text)
    needle = keyword.casefold()

    hits: List[Tuple[int, int]] = []
    start = 0
    while True:
        idx = lowered.find(needle, start)
        if idx == -1:
            break
        hits.append((idx, idx + len(needle)))
        start = idx + 1
    return hits


def _snippet(text: str, start: int, end: int, snippet_chars: int) -> str:
    half = max(20, snippet_chars // 2)
    s = max(0, start - half)
    e = min(len(text), end + half)
    snippet = text[s:e]
    snippet = snippet.replace("\n", " ")
    snippet = re.sub(r"\s{2,}", " ", snippet).strip()
    return snippet


def _clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


def _nearest_agenda_item(items: List[AgendaItem], pos: int) -> Optional[AgendaItem]:
    if not items:
        return None
    starts = [i.start for i in items]
    idx = bisect.bisect_right(starts, pos) - 1
    if idx < 0:
        return None
    return items[idx]


def _nearest_attachment(items: List[Attachment], pos: int) -> Optional[Attachment]:
    if not items:
        return None
    starts = [i.start for i in items]
    idx = bisect.bisect_right(starts, pos) - 1
    if idx < 0:
        return None
    att = items[idx]
    if att.start <= pos < att.end:
        return att
    return None


def _extract_rationale_near(text: str, anchor_start: int, window_chars: int = 1800) -> Optional[str]:
    """Try to extract a short 'why' sentence near an agenda item header."""
    window = text[anchor_start : min(len(text), anchor_start + window_chars)]
    window = re.sub(r"\s+", " ", window).strip()

    # Look for common staff-report phrasing.
    m = re.search(
        r"(?i)(to address|to allow|to create|to amend|to update|to revise|to modify|to change|in order to)[^.]{0,220}\.",
        window,
    )
    if not m:
        return None
    return _clean_line(m.group(0))


def _rule_explanation(
    rule_result: Dict[str, Any],
    sources: Dict[str, str],
    agenda_by_source: Dict[str, List[AgendaItem]],
    attachments_by_source: Dict[str, List[Attachment]],
) -> Dict[str, Any]:
    """Attach a human readable explanation and agenda references to a rule result."""
    if not rule_result.get("alert"):
        rule_result["explanation"] = None
        rule_result["agenda_refs"] = []
        rule_result["attachment_refs"] = []
        rule_result["rationale"] = None
        return rule_result

    evidence = rule_result.get("evidence") or []
    agenda_refs: List[Dict[str, str]] = []
    attachment_refs: List[Dict[str, Any]] = []
    seen = set()
    seen_attachments = set()
    rationales: List[str] = []

    for ev in evidence:
        source_name = ev.get("source")
        if not source_name or source_name not in sources:
            continue
        items = agenda_by_source.get(source_name) or []
        attachments = attachments_by_source.get(source_name) or []

        start_pos = int(ev.get("start", 0))

        last_agenda_end = items[-1].end if items else 0
        nearest = _nearest_agenda_item(items, start_pos)
        if nearest and start_pos <= last_agenda_end:
            ev["bucket"] = "agenda_item"
            ev["agenda_item"] = {"item_id": nearest.item_id, "title": nearest.title}
            key = (nearest.item_id, nearest.title)
            if key not in seen:
                seen.add(key)
                agenda_refs.append({"item_id": nearest.item_id, "title": nearest.title})
                why = _extract_rationale_near(sources[source_name], nearest.start)
                if why:
                    rationales.append(why)
            continue

        nearest_attachment = _nearest_attachment(attachments, start_pos)
        if nearest_attachment:
            ev["bucket"] = "attachment"
            ev["attachment"] = {
                "attachment_id": nearest_attachment.attachment_id,
                "title": nearest_attachment.title,
                "type_guess": nearest_attachment.type_guess,
            }
            akey = (nearest_attachment.attachment_id, nearest_attachment.title)
            if akey not in seen_attachments:
                seen_attachments.add(akey)
                attachment_refs.append(
                    {
                        "attachment_id": nearest_attachment.attachment_id,
                        "title": nearest_attachment.title,
                        "type_guess": nearest_attachment.type_guess,
                    }
                )
        else:
            ev["bucket"] = None

    snippet_texts = [str(ev.get("snippet", "")) for ev in evidence if ev.get("snippet")]

    def extract_unique(pattern: str, max_items: int = 3) -> List[str]:
        found: List[str] = []
        seen_local = set()
        rx = re.compile(pattern)
        for s in snippet_texts:
            m = rx.search(s)
            if not m:
                continue
            val = _clean_line(m.group(0))
            val = re.sub(r"\s{2,}", " ", val)
            if val and val not in seen_local:
                seen_local.add(val)
                found.append(val)
            if len(found) >= max_items:
                break
        return found

    combined = " ".join(snippet_texts[:2]).lower()
    attachment_like = any(
        marker in combined
        for marker in (
            " plat ",
            "phase 'a'",
            "sq. ft",
            "township",
            "range",
            "salt lake base",
            "meridian",
        )
    )

    attachment_evidence = [ev for ev in evidence if ev.get("bucket") == "attachment"]
    attachment_type = None
    if attachment_evidence:
        attachment_type = ((attachment_evidence[0].get("attachment") or {}).get("type_guess"))

    if attachment_evidence or attachment_refs or attachment_like:
        agenda_refs = []
        # Try to surface a more concrete phrase.
        plat_details = extract_unique(r"(?i)SUNSET\s+FLATS[^,\n]{0,60}")
        if attachment_type == "plat" and plat_details:
            explanation = f"Mention appears in an attachment/exhibit (type: plat), e.g. '{plat_details[0]}'."
        elif attachment_type:
            explanation = f"Mention appears in an attachment/exhibit (type: {attachment_type}) included in the packet."
        else:
            explanation = "Mention appears in an attachment/exhibit included in the packet."
    elif agenda_refs:
        refs = "; ".join([f"{r['item_id']}: {r['title']}" for r in agenda_refs[:3]])
        explanation = f"Mention appears under agenda item(s): {refs}."
    else:
        # Fallback for attachments/exhibits where headings aren't captured.
        explanation = "Mention appears in the packet text (could be in attachments or supporting exhibits)."

    # Rule-specific enrichment.
    details: List[str] = []
    if rule_result.get("rule_id") == "city_code_changes_residential":
        details = extract_unique(r"(?i)An\s+Ordinance[^\n]{0,220}")
        if details:
            explanation = "City code changes are being considered via ordinance/public hearing items. Examples: " + "; ".join(details[:3])
    elif rule_result.get("rule_id") == "neighborhood_sunset_flats":
        details = extract_unique(r"(?i)SUNSET\s+FLATS[^\n]{0,80}")

    rule_result["agenda_refs"] = agenda_refs
    rule_result["attachment_refs"] = attachment_refs
    rule_result["explanation"] = explanation
    rule_result["rationale"] = rationales[0] if rationales else None
    rule_result["details"] = details
    return rule_result


def _prefilter_from_rule_results(rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact, UI-friendly prefilter view.

    B2: fast prefiltering should flag candidate agenda items/attachments and
    include evidence snippets for each hit.
    """

    out_rules: List[Dict[str, Any]] = []
    total_candidates = 0

    for rr in rule_results:
        evidence = rr.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        agenda_map: Dict[str, Dict[str, Any]] = {}
        attachment_map: Dict[str, Dict[str, Any]] = {}

        def add_agenda_candidate(item_id: str, title: str, ev: Dict[str, Any]) -> None:
            key = item_id
            entry = agenda_map.get(key)
            if entry is None:
                entry = {"item_id": item_id, "title": title, "hits": 0, "evidence": []}
                agenda_map[key] = entry
            entry["hits"] += 1
            entry["evidence"].append(
                {
                    "source": ev.get("source"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "snippet": ev.get("snippet"),
                }
            )

        def add_attachment_candidate(attachment_id: str, title: str, type_guess: Optional[str], ev: Dict[str, Any]) -> None:
            key = attachment_id
            entry = attachment_map.get(key)
            if entry is None:
                entry = {
                    "attachment_id": attachment_id,
                    "title": title,
                    "type_guess": type_guess,
                    "hits": 0,
                    "evidence": [],
                }
                attachment_map[key] = entry
            entry["hits"] += 1
            entry["evidence"].append(
                {
                    "source": ev.get("source"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "snippet": ev.get("snippet"),
                }
            )

        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            bucket = ev.get("bucket")
            if bucket == "agenda_item":
                ai = ev.get("agenda_item") or {}
                if isinstance(ai, dict):
                    item_id = ai.get("item_id")
                    title = ai.get("title")
                    if isinstance(item_id, str) and isinstance(title, str):
                        add_agenda_candidate(item_id, title, ev)
            elif bucket == "attachment":
                att = ev.get("attachment") or {}
                if isinstance(att, dict):
                    attachment_id = att.get("attachment_id")
                    title = att.get("title")
                    type_guess = att.get("type_guess")
                    if isinstance(attachment_id, str) and isinstance(title, str):
                        add_attachment_candidate(
                            attachment_id,
                            title,
                            type_guess if isinstance(type_guess, str) else None,
                            ev,
                        )

        agenda_candidates = list(agenda_map.values())
        attachment_candidates = list(attachment_map.values())
        # Keep stable order but prefer higher-hit candidates first.
        agenda_candidates.sort(key=lambda x: int(x.get("hits", 0)), reverse=True)
        attachment_candidates.sort(key=lambda x: int(x.get("hits", 0)), reverse=True)

        total_candidates += len(agenda_candidates) + len(attachment_candidates)

        out_rules.append(
            {
                "rule_id": rr.get("rule_id"),
                "description": rr.get("description"),
                "type": rr.get("type"),
                "enabled": rr.get("enabled", True),
                "alert": rr.get("alert", False),
                "hits": rr.get("hits", 0),
                "agenda_item_candidates": agenda_candidates,
                "attachment_candidates": attachment_candidates,
            }
        )

    return {
        "rules": out_rules,
        "candidate_count": total_candidates,
    }


def _dedupe_evidence(evidence: List[Evidence]) -> List[Evidence]:
    # Keep stable order; dedupe by (source,start,end)
    seen = set()
    out: List[Evidence] = []
    for ev in evidence:
        key = (ev.source, ev.start, ev.end)
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def evaluate_rule(
    rule: Dict[str, Any],
    sources: Dict[str, str],
    evidence_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    rule_type = rule.get("type")
    enabled = bool(rule.get("enabled", True))
    if not enabled:
        return {"rule_id": rule.get("id"), "enabled": False, "alert": False, "hits": 0, "evidence": []}

    snippet_chars = int(evidence_cfg.get("snippet_chars", 260))
    max_snips = int(evidence_cfg.get("max_snippets_per_rule", 5))

    keywords: List[str] = [k for k in (rule.get("keywords") or []) if isinstance(k, str) and k.strip()]
    min_hits = int(rule.get("min_hits", 1))

    total_hits = 0
    evidence: List[Evidence] = []

    if rule_type == "keyword_any":
        for source_name, text in sources.items():
            for kw in keywords:
                for start, end in _find_keyword_hits(text, kw):
                    total_hits += 1
                    if len(evidence) < max_snips:
                        evidence.append(
                            Evidence(
                                source=source_name,
                                start=start,
                                end=end,
                                snippet=_snippet(text, start, end, snippet_chars),
                            )
                        )

        evidence = _dedupe_evidence(evidence)
        return {
            "rule_id": rule.get("id"),
            "description": rule.get("description"),
            "type": rule_type,
            "alert": total_hits >= min_hits,
            "hits": total_hits,
            "min_hits": min_hits,
            "evidence": [ev.__dict__ for ev in evidence],
        }

    if rule_type == "keyword_with_context":
        ctx_keywords: List[str] = [k for k in (rule.get("context_keywords") or []) if isinstance(k, str) and k.strip()]
        window_chars = int(rule.get("window_chars", 300))

        for source_name, text in sources.items():
            lowered = _lower(text)
            for kw in keywords:
                for start, end in _find_keyword_hits(text, kw):
                    window_start = max(0, start - window_chars)
                    window_end = min(len(text), end + window_chars)
                    window = lowered[window_start:window_end]

                    if any(ctx.casefold() in window for ctx in ctx_keywords):
                        total_hits += 1
                        if len(evidence) < max_snips:
                            evidence.append(
                                Evidence(
                                    source=source_name,
                                    start=start,
                                    end=end,
                                    snippet=_snippet(text, start, end, snippet_chars),
                                )
                            )

        evidence = _dedupe_evidence(evidence)
        return {
            "rule_id": rule.get("id"),
            "description": rule.get("description"),
            "type": rule_type,
            "alert": total_hits >= min_hits,
            "hits": total_hits,
            "min_hits": min_hits,
            "window_chars": window_chars,
            "evidence": [ev.__dict__ for ev in evidence],
        }

    return {
        "rule_id": rule.get("id"),
        "description": rule.get("description"),
        "type": rule_type,
        "alert": False,
        "hits": 0,
        "error": f"Unknown rule type: {rule_type}",
        "evidence": [],
    }


def build_sources(text_path: Optional[Path], pdf_path: Optional[Path]) -> Dict[str, str]:
    sources: Dict[str, str] = {}

    if text_path is not None:
        sources["text"] = read_text_file(text_path)

    if pdf_path is not None:
        try:
            _engine, text = extract_pdf_text_canonical(pdf_path)
        except PdfExtractionError as e:
            raise SystemExit(str(e)) from e
        sources["pdf"] = text

    return sources


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Minutes extraction + alerting spike")
    parser.add_argument("--meeting-id", default=None, help="Identifier like YYYY-MM-DD (optional; auto-generated if omitted)")
    parser.add_argument("--text", type=str, default=None, help="Path to plain text minutes")
    parser.add_argument("--pdf", type=str, default=None, help="Path to PDF minutes")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Path to interest profile YAML (optional; defaults to local XDG config or ./interest_profile.yaml)",
    )
    parser.add_argument(
        "--init-profile",
        action="store_true",
        help="Create a starter interest profile at the resolved profile path and exit",
    )
    parser.add_argument(
        "--overwrite-profile",
        action="store_true",
        help="With --init-profile, overwrite an existing profile file",
    )
    parser.add_argument(
        "--print-profile-path",
        action="store_true",
        help="Print the resolved profile path and exit",
    )
    parser.add_argument("--out", type=str, default=None, help="Output JSON path")
    parser.add_argument(
        "--agenda-out",
        type=str,
        default=None,
        help="If set, write full agenda_items.json (id/title/body/start/end) to this path",
    )
    parser.add_argument("--store-dir", type=str, default=None, help="If set, import and store the meeting under this directory")
    parser.add_argument("--import-only", action="store_true", help="If set with --store-dir, only import/store (skip rule evaluation)")

    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve a minimal local web UI (F1) showing imported meetings from the SQLite index in --store-dir",
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for --serve (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for --serve (default: 8000)")

    parser.add_argument(
        "--summarize-first-item",
        action="store_true",
        help="If set, summarize the first extracted agenda item using a local LLM provider",
    )
    parser.add_argument(
        "--summarize-all-items",
        action="store_true",
        help="If set, summarize each extracted agenda item (Pass A) using a local LLM provider",
    )
    parser.add_argument(
        "--classify-relevance",
        action="store_true",
        help="If set, classify agenda items against interest rules (Pass B) and emit a things_you_care_about list",
    )
    parser.add_argument(
        "--summarize-meeting",
        action="store_true",
        help="If set, produce a meeting-level summary (Pass C) from available Pass A/Pass B outputs",
    )
    parser.add_argument("--llm-provider", type=str, default=None, help="LLM provider (default: ollama)")
    parser.add_argument("--llm-endpoint", type=str, default=None, help="LLM endpoint base URL (default: http://localhost:11434)")
    parser.add_argument("--llm-model", type=str, default=None, help="LLM model name (required for summarization)")
    parser.add_argument("--llm-timeout-s", type=float, default=None, help="LLM request timeout seconds (default: 120)")
    parser.add_argument(
        "--llm-use-toon",
        action="store_true",
        help="If set with --summarize-first-item/--summarize-all-items, send/receive structured TOON-ish YAML at the LLM boundary",
    )

    args = parser.parse_args(argv)

    if args.serve:
        from .web import serve

        if not args.store_dir:
            parser.error("--serve requires --store-dir")
        store_dir = Path(args.store_dir)
        print(f"Serving meeting list at http://{args.host}:{int(args.port)}/ (store: {store_dir})")
        serve(store_dir=store_dir, host=str(args.host), port=int(args.port))
        return 0

    # For normal runs, we keep backwards-compatible resolution (XDG if present,
    # else repo-local interest_profile.yaml if it exists).
    # For --init-profile, prefer initializing in XDG config by default.
    profile_path = resolve_profile_path(args.profile, prefer_xdg=bool(args.init_profile))

    if args.print_profile_path:
        print(profile_path)
        return 0

    if args.init_profile:
        init_profile(profile_path, overwrite=bool(args.overwrite_profile))
        print(f"Initialized interest profile at {profile_path}")
        return 0

    text_path = Path(args.text) if args.text else None
    pdf_path = Path(args.pdf) if args.pdf else None

    if text_path is None and pdf_path is None:
        parser.error("Provide at least one of --text or --pdf")

    meeting_id = args.meeting_id
    if meeting_id is None:
        meeting_id = generate_meeting_id(pdf_path, text_path)
    stored_meeting_dir: Optional[str] = None
    if args.store_dir:
        try:
            imported = import_meeting(
                store_dir=Path(args.store_dir),
                pdf_path=pdf_path,
                text_path=text_path,
                meeting_id=meeting_id,
            )
            meeting_id = imported.meeting_id
            stored_meeting_dir = str(imported.meeting_dir)
            print(f"Imported meeting {meeting_id} -> {imported.meeting_dir}")
            if args.import_only:
                return 0
        except IngestionError as e:
            print(f"Import failed: {e}")
            return 2

    try:
        profile = load_profile(profile_path)
    except ProfileError as e:
        print(str(e))
        return 2

    llm_profile = profile.get("llm") or {}
    if not isinstance(llm_profile, dict):
        llm_profile = {}

    rules: List[Dict[str, Any]] = profile.get("rules") or []
    evidence_cfg: Dict[str, Any] = (profile.get("output") or {}).get("evidence") or {}

    sources = build_sources(text_path, pdf_path)
    if not sources:
        raise SystemExit("No text extracted. If the PDF is scanned, OCR is not supported yet.")

    results = [evaluate_rule(rule, sources, evidence_cfg) for rule in rules]
    any_alert = any(r.get("alert") for r in results)

    agenda_by_source: Dict[str, List[AgendaItem]] = {k: extract_agenda_items(v) for k, v in sources.items()}
    attachments_by_source: Dict[str, List[Attachment]] = {
        k: extract_attachments(v, agenda_end=max((i.end for i in agenda_by_source.get(k) or []), default=0))
        for k, v in sources.items()
    }
    results = [_rule_explanation(r, sources, agenda_by_source, attachments_by_source) for r in results]

    prefilter = _prefilter_from_rule_results(results)

    # Prefer a concise agenda list from the best available source.
    preferred_source = None
    for candidate in ("pdf", "text"):
        if candidate in sources:
            preferred_source = candidate
            break

    agenda_items_preview: List[Dict[str, Any]] = []
    agenda_items_full: List[Dict[str, Any]] = []
    attachments_preview: List[Dict[str, Any]] = []
    if preferred_source:
        agenda_items_full = [
            {
                "item_id": i.item_id,
                "title": i.title,
                "body_text": i.body_text,
                "start": i.start,
                "end": i.end,
            }
            for i in (agenda_by_source.get(preferred_source) or [])
        ]
        agenda_items_preview = [
            {
                "item_id": i.item_id,
                "title": i.title,
                # Keep CLI output compact; full bodies are stored during import.
                "body_text": (i.body_text[:2000] + "\n[...truncated...]") if len(i.body_text) > 2000 else i.body_text,
            }
            for i in (agenda_by_source.get(preferred_source) or [])[:40]
        ]

        attachments_preview = [
            {
                "attachment_id": a.attachment_id,
                "title": a.title,
                "type_guess": a.type_guess,
                "body_text": (a.body_text[:2000] + "\n[...truncated...]") if len(a.body_text) > 2000 else a.body_text,
            }
            for a in (attachments_by_source.get(preferred_source) or [])[:30]
        ]

    summarize_failed = False
    llm_summary_run: Optional[Dict[str, Any]] = None
    if args.summarize_first_item or args.summarize_all_items:
        provider = args.llm_provider or os.environ.get("COUNCILSENSE_LLM_PROVIDER") or llm_profile.get("provider") or "ollama"
        endpoint = (
            args.llm_endpoint
            or os.environ.get("COUNCILSENSE_LLM_ENDPOINT")
            or llm_profile.get("endpoint")
            or "http://localhost:11434"
        )
        model = args.llm_model or os.environ.get("COUNCILSENSE_LLM_MODEL") or llm_profile.get("model")
        timeout_s = (
            args.llm_timeout_s
            or (float(os.environ["COUNCILSENSE_LLM_TIMEOUT_S"]) if os.environ.get("COUNCILSENSE_LLM_TIMEOUT_S") else None)
            or llm_profile.get("timeout_s")
            or 120
        )

        run_generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prompt_template = SUMMARIZE_AGENDA_ITEM_TOON if args.llm_use_toon else SUMMARIZE_AGENDA_ITEM_BULLETS
        llm_summary_run = {
            "generated_at": run_generated_at,
            "llm": {
                "provider": str(provider),
                "endpoint": str(endpoint),
                "model": str(model).strip() if isinstance(model, str) else None,
                "timeout_s": float(timeout_s),
            },
            "prompt_template": {
                "id": prompt_template.id,
                "version": int(prompt_template.version),
            },
        }

        def attach_error(idx: int, err: Dict[str, Any]) -> None:
            nonlocal summarize_failed
            summarize_failed = True
            if 0 <= idx < len(agenda_items_full):
                agenda_items_full[idx]["summary_error"] = err
                agenda_items_full[idx]["summary"] = []
                agenda_items_full[idx]["pass_a"] = {
                    "summary": [],
                    "actions": [],
                    "entities": [],
                    "key_terms": [],
                    "citations": [],
                }
            if 0 <= idx < len(agenda_items_preview):
                agenda_items_preview[idx]["summary_error"] = err
                agenda_items_preview[idx]["summary"] = []
                agenda_items_preview[idx]["pass_a"] = {
                    "summary": [],
                    "actions": [],
                    "entities": [],
                    "key_terms": [],
                    "citations": [],
                }


        if not model or not isinstance(model, str) or not model.strip():
            for idx in range(min(len(agenda_items_full), 1 if args.summarize_first_item else len(agenda_items_full))):
                attach_error(
                    idx,
                    {
                        "code": "llm_model_missing",
                        "message": "LLM model is required for summarization (set llm.model in the profile or pass --llm-model).",
                        "retryable": False,
                        "provider": str(provider),
                    },
                )
            print("LLM summarization failed: missing model config.", file=sys.stderr)
        elif not agenda_items_full:
            attach_error(
                0,
                {
                    "code": "no_agenda_items",
                    "message": "No agenda items detected; cannot summarize.",
                    "retryable": False,
                    "provider": str(provider),
                    "model": str(model).strip(),
                },
            )
            print("LLM summarization failed: no agenda items detected.", file=sys.stderr)
        else:
            try:
                cfg = ProviderConfig(
                    provider=str(provider),
                    endpoint=str(endpoint),
                    model=str(model).strip(),
                    timeout_s=float(timeout_s),
                )
                llm = create_llm_provider(cfg)
            except Exception as e:
                attach_error(
                    0,
                    {
                        "code": "llm_error",
                        "message": "LLM provider initialization failed.",
                        "retryable": False,
                        "provider": str(provider),
                        "model": str(model).strip() if isinstance(model, str) else None,
                        "details": {"exception_type": type(e).__name__},
                    },
                )
                llm = None

            if llm is not None:
                db_path: Optional[Path] = None
                if args.store_dir:
                    try:
                        db_path = Path(args.store_dir).resolve() / DB_FILENAME
                    except Exception:
                        db_path = None

                indices = [0] if args.summarize_first_item else list(range(len(agenda_items_full)))
                for idx in indices:
                    try:
                        title = str(agenda_items_full[idx].get("title") or "").strip()
                        body_text = str(agenda_items_full[idx].get("body_text") or "").strip()
                        body_for_llm = body_text
                        if len(body_for_llm) > 12000:
                            body_for_llm = body_for_llm[:12000] + "\n[...truncated...]"

                        if args.llm_use_toon:
                            prompt_template = SUMMARIZE_AGENDA_ITEM_TOON
                            input_json = {
                                "meeting_id": meeting_id,
                                "agenda_item": {
                                    "item_id": str(agenda_items_full[idx].get("item_id") or ""),
                                    "title": title,
                                    "body_text": body_for_llm,
                                },
                            }
                            input_toon = encode_json_to_toon(input_json)
                            prompt = build_summarize_agenda_item_toon_prompt(input_toon=input_toon)

                            cache_hit = False
                            cache_key: Optional[str] = None
                            cached_obj: Optional[object] = None
                            if db_path is not None:
                                cache_input = {
                                    "kind": "summarize_agenda_item_toon",
                                    "input_json": input_json,
                                    "prompt_id": prompt_template.id,
                                    "prompt_version": int(prompt_template.version),
                                    "model": {
                                        "provider": str(provider),
                                        "endpoint": str(endpoint),
                                        "model": str(model).strip(),
                                    },
                                }
                                cache_key = stable_hash_json(cache_input)
                                cached_obj = get_llm_cache(db_path=db_path, cache_key=cache_key)

                            if isinstance(cached_obj, dict) and isinstance(cached_obj.get("output_json"), dict):
                                output_json = cached_obj.get("output_json")
                                output_toon = str(cached_obj.get("output_toon") or "")
                                cache_hit = True
                            else:
                                output_toon = llm.generate_text(prompt=prompt)
                                output_json = decode_toon_to_json(output_toon)
                                if db_path is not None and cache_key is not None:
                                    try:
                                        put_llm_cache(
                                            db_path=db_path,
                                            cache_key=cache_key,
                                            kind="summarize_agenda_item_toon",
                                            obj={
                                                "output_toon": output_toon,
                                                "output_json": output_json,
                                            },
                                            model_provider=str(provider),
                                            model_endpoint=str(endpoint),
                                            model=str(model).strip(),
                                            prompt_id=prompt_template.id,
                                            prompt_version=int(prompt_template.version),
                                        )
                                    except Exception:
                                        pass

                            bullets = _normalize_str_list(output_json.get("summary"))
                            actions = _normalize_str_list(output_json.get("actions"))
                            entities = _normalize_str_list(output_json.get("entities"))
                            key_terms = _normalize_str_list(output_json.get("key_terms"))
                            citations = _ensure_evidence_citation(body_text, _normalize_str_list(output_json.get("citations")))

                            pass_a = {
                                "summary": bullets,
                                "actions": actions,
                                "entities": entities,
                                "key_terms": key_terms,
                                "citations": citations,
                            }

                            roundtrip = {
                                "mode": "toon",
                                "generated_at": run_generated_at,
                                "llm": {
                                    "provider": str(provider),
                                    "endpoint": str(endpoint),
                                    "model": str(model).strip(),
                                    "timeout_s": float(timeout_s),
                                },
                                "prompt_template": {
                                    "id": prompt_template.id,
                                    "version": int(prompt_template.version),
                                },
                                "cache": {
                                    "hit": bool(cache_hit),
                                    "key": cache_key,
                                },
                                "input_json": input_json,
                                "input_toon": input_toon,
                                "output_toon": output_toon,
                                "output_json": output_json,
                                "validated": True,
                            }
                            agenda_items_full[idx]["llm_roundtrip"] = roundtrip
                            if idx < len(agenda_items_preview):
                                agenda_items_preview[idx]["llm_roundtrip"] = roundtrip
                        else:
                            prompt_template = SUMMARIZE_AGENDA_ITEM_BULLETS

                            cache_hit = False
                            cache_key: Optional[str] = None
                            cached_obj: Optional[object] = None
                            if db_path is not None:
                                cache_input = {
                                    "kind": "summarize_agenda_item_bullets",
                                    "title": title,
                                    "body_text": body_for_llm,
                                    "prompt_id": prompt_template.id,
                                    "prompt_version": int(prompt_template.version),
                                    "model": {
                                        "provider": str(provider),
                                        "endpoint": str(endpoint),
                                        "model": str(model).strip(),
                                    },
                                }
                                cache_key = stable_hash_json(cache_input)
                                cached_obj = get_llm_cache(db_path=db_path, cache_key=cache_key)

                            if isinstance(cached_obj, dict) and isinstance(cached_obj.get("bullets"), list):
                                bullets = [b for b in cached_obj.get("bullets") if isinstance(b, str) and b.strip()]
                                cache_hit = bool(bullets)
                            else:
                                res = llm.summarize_agenda_item(title=title, body_text=body_for_llm)
                                bullets = res.bullets
                                if db_path is not None and cache_key is not None:
                                    try:
                                        put_llm_cache(
                                            db_path=db_path,
                                            cache_key=cache_key,
                                            kind="summarize_agenda_item_bullets",
                                            obj={"bullets": bullets, "raw_text": getattr(res, "raw_text", None)},
                                            model_provider=str(provider),
                                            model_endpoint=str(endpoint),
                                            model=str(model).strip(),
                                            prompt_id=prompt_template.id,
                                            prompt_version=int(prompt_template.version),
                                        )
                                    except Exception:
                                        pass
                            actions = _extract_actions_simple(title, body_text)
                            entities = _extract_entities_simple(f"{title}\n{body_text}")
                            key_terms = _extract_key_terms_simple(title, body_text)
                            citations = _ensure_evidence_citation(body_text, [])
                            pass_a = {
                                "summary": bullets,
                                "actions": actions,
                                "entities": entities,
                                "key_terms": key_terms,
                                "citations": citations,
                            }

                        pass_a["provenance"] = {
                            "generated_at": run_generated_at,
                            "llm": {
                                "provider": str(provider),
                                "endpoint": str(endpoint),
                                "model": str(model).strip(),
                                "timeout_s": float(timeout_s),
                            },
                            "prompt_template": {
                                "id": prompt_template.id,
                                "version": int(prompt_template.version),
                            },
                            "cache": {
                                "hit": bool(cache_hit),
                                "key": cache_key,
                            },
                        }

                        # Attach in both full + preview. Keep a convenient top-level summary alias.
                        agenda_items_full[idx]["pass_a"] = pass_a
                        agenda_items_full[idx]["summary"] = pass_a.get("summary") or []
                        if idx < len(agenda_items_preview):
                            agenda_items_preview[idx]["pass_a"] = pass_a
                            agenda_items_preview[idx]["summary"] = pass_a.get("summary") or []
                    except LLMError as e:
                        attach_error(idx, e.to_dict())
                        print(f"LLM summarization failed for agenda item #{idx + 1}: {e.message}", file=sys.stderr)
                    except ToonDecodeError as e:
                        attach_error(
                            idx,
                            {
                                "code": "toon_decode_error",
                                "message": str(e),
                                "retryable": False,
                                "provider": str(provider),
                                "model": str(model).strip(),
                            },
                        )
                        if 0 <= idx < len(agenda_items_full):
                            agenda_items_full[idx]["llm_roundtrip"] = {
                                "mode": "toon",
                                "validated": False,
                                "error": str(e),
                            }
                        if 0 <= idx < len(agenda_items_preview):
                            agenda_items_preview[idx]["llm_roundtrip"] = {
                                "mode": "toon",
                                "validated": False,
                                "error": str(e),
                            }
                        print(f"LLM TOON decode failed for agenda item #{idx + 1}: {e}", file=sys.stderr)
                    except Exception as e:
                        attach_error(
                            idx,
                            {
                                "code": "llm_error",
                                "message": "LLM summarization failed due to an unexpected error.",
                                "retryable": False,
                                "provider": str(provider),
                                "model": str(model).strip(),
                                "details": {"exception_type": type(e).__name__},
                            },
                        )
                        print(
                            f"LLM summarization failed for agenda item #{idx + 1}: {type(e).__name__}",
                            file=sys.stderr,
                        )

    # If this run imported a meeting folder, persist Pass A summaries there as an artifact.
    if stored_meeting_dir and (args.summarize_first_item or args.summarize_all_items) and agenda_items_full:
        try:
            meeting_dir = Path(stored_meeting_dir)
            out_items: List[Dict[str, Any]] = []
            for item in agenda_items_full:
                if item.get("pass_a"):
                    out_items.append(
                        {
                            "item_id": item.get("item_id"),
                            "title": item.get("title"),
                            "pass_a": item.get("pass_a"),
                        }
                    )
            summaries_path = meeting_dir / "agenda_pass_a.json"
            summaries_path.write_text(json.dumps(out_items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            meeting_json_path = meeting_dir / "meeting.json"
            if meeting_json_path.exists():
                meeting = json.loads(meeting_json_path.read_text(encoding="utf-8"))
                prompt_template = SUMMARIZE_AGENDA_ITEM_TOON if args.llm_use_toon else SUMMARIZE_AGENDA_ITEM_BULLETS
                meeting["agenda_pass_a"] = {
                    "stored_path": str(summaries_path),
                    "count": len(out_items),
                    "mode": "toon" if args.llm_use_toon else "bullets+heuristics",
                    "llm": {
                        "provider": str(provider),
                        "endpoint": str(endpoint),
                        "model": str(model).strip() if isinstance(model, str) else None,
                        "timeout_s": float(timeout_s),
                    },
                    "prompt_template": {
                        "id": prompt_template.id,
                        "version": int(prompt_template.version),
                    },
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                meeting_json_path.write_text(json.dumps(meeting, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            # Non-fatal: CLI output still contains summaries.
            pass

    # D2: Pass B interest classification.
    pass_b_failed = False
    things_you_care_about: List[Dict[str, Any]] = []
    if args.classify_relevance and agenda_items_full:
        semantic_agenda: Dict[str, Dict[str, Any]] = {}
        semantic_attachments: Dict[str, Dict[str, Any]] = {}

        # J1: optional semantic precision pass (only if an LLM model is configured).
        sem_provider = args.llm_provider or os.environ.get("COUNCILSENSE_LLM_PROVIDER") or llm_profile.get("provider") or "ollama"
        sem_endpoint = (
            args.llm_endpoint
            or os.environ.get("COUNCILSENSE_LLM_ENDPOINT")
            or llm_profile.get("endpoint")
            or "http://localhost:11434"
        )
        sem_model = args.llm_model or os.environ.get("COUNCILSENSE_LLM_MODEL") or llm_profile.get("model")
        sem_timeout_s = (
            args.llm_timeout_s
            or (float(os.environ["COUNCILSENSE_LLM_TIMEOUT_S"]) if os.environ.get("COUNCILSENSE_LLM_TIMEOUT_S") else None)
            or llm_profile.get("timeout_s")
            or 120
        )

        sem_llm = None
        sem_generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        sem_db_path: Optional[Path] = None
        if args.store_dir:
            try:
                sem_db_path = Path(args.store_dir).resolve() / DB_FILENAME
            except Exception:
                sem_db_path = None

        if isinstance(sem_model, str) and sem_model.strip():
            try:
                sem_llm = create_llm_provider(
                    ProviderConfig(
                        provider=str(sem_provider),
                        endpoint=str(sem_endpoint),
                        model=str(sem_model).strip(),
                        timeout_s=float(sem_timeout_s),
                    )
                )
            except Exception:
                sem_llm = None

        if sem_llm is not None and preferred_source:
            rule_cfg_by_id: Dict[str, Dict[str, Any]] = {}
            for r in rules:
                if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("id"):
                    rule_cfg_by_id[str(r.get("id"))] = r

            agenda_by_id: Dict[str, Dict[str, Any]] = {}
            for it in agenda_items_full:
                if isinstance(it, dict) and isinstance(it.get("item_id"), str):
                    agenda_by_id[str(it.get("item_id"))] = it

            attachments_by_id: Dict[str, Attachment] = {a.attachment_id: a for a in (attachments_by_source.get(preferred_source) or [])}

            for rr in (prefilter.get("rules") or []):
                if not isinstance(rr, dict):
                    continue
                rule_id = rr.get("rule_id")
                if not isinstance(rule_id, str) or not rule_id:
                    continue

                rule_cfg = rule_cfg_by_id.get(rule_id) or {}
                desc = rule_cfg.get("description") if isinstance(rule_cfg.get("description"), str) else rr.get("description")
                if not isinstance(desc, str) or not desc.strip():
                    desc = rule_id
                kws = rule_cfg.get("keywords") if isinstance(rule_cfg.get("keywords"), list) else []

                agenda_candidates = rr.get("agenda_item_candidates") or []
                if isinstance(agenda_candidates, list):
                    for cand in agenda_candidates:
                        if sem_llm is None:
                            break
                        if not isinstance(cand, dict):
                            continue
                        item_id = cand.get("item_id")
                        if not isinstance(item_id, str) or not item_id:
                            continue
                        it = agenda_by_id.get(item_id)
                        if not isinstance(it, dict):
                            continue
                        title = str(it.get("title") or "")
                        body = str(it.get("body_text") or "")
                        evidence_snips = []
                        evs = cand.get("evidence")
                        if isinstance(evs, list):
                            for ev in evs:
                                if isinstance(ev, dict):
                                    sn = ev.get("snippet")
                                    if isinstance(sn, str) and sn.strip():
                                        evidence_snips.append(sn.strip())
                                if len(evidence_snips) >= 3:
                                    break

                        try:
                            sem = _semantic_classify_relevance(
                                llm=sem_llm,
                            db_path=sem_db_path,
                            provider=str(sem_provider),
                            endpoint=str(sem_endpoint),
                            model=str(sem_model).strip(),
                            timeout_s=float(sem_timeout_s),
                            generated_at=sem_generated_at,
                            category_id=rule_id,
                            category_description=str(desc),
                            category_keywords=[k for k in kws if isinstance(k, str)],
                            candidate_kind="agenda_item",
                            candidate_title=f"{item_id}: {title}" if item_id else title,
                            candidate_text=f"{title}\n\n{body}".strip(),
                            evidence_snippets=evidence_snips,
                            )
                        except NotImplementedError:
                            sem_llm = None
                            break
                        semantic_agenda.setdefault(item_id, {})[rule_id] = sem

                if sem_llm is None:
                    break

                attachment_candidates = rr.get("attachment_candidates") or []
                if isinstance(attachment_candidates, list):
                    for cand in attachment_candidates:
                        if sem_llm is None:
                            break
                        if not isinstance(cand, dict):
                            continue
                        attachment_id = cand.get("attachment_id")
                        if not isinstance(attachment_id, str) or not attachment_id:
                            continue
                        att = attachments_by_id.get(attachment_id)
                        if att is None:
                            continue
                        evidence_snips = []
                        evs = cand.get("evidence")
                        if isinstance(evs, list):
                            for ev in evs:
                                if isinstance(ev, dict):
                                    sn = ev.get("snippet")
                                    if isinstance(sn, str) and sn.strip():
                                        evidence_snips.append(sn.strip())
                                if len(evidence_snips) >= 3:
                                    break

                        try:
                            sem = _semantic_classify_relevance(
                                llm=sem_llm,
                            db_path=sem_db_path,
                            provider=str(sem_provider),
                            endpoint=str(sem_endpoint),
                            model=str(sem_model).strip(),
                            timeout_s=float(sem_timeout_s),
                            generated_at=sem_generated_at,
                            category_id=rule_id,
                            category_description=str(desc),
                            category_keywords=[k for k in kws if isinstance(k, str)],
                            candidate_kind="attachment",
                            candidate_title=f"{att.attachment_id}: {att.title}",
                            candidate_text=f"{att.title}\n\n{att.body_text}".strip(),
                            evidence_snippets=evidence_snips,
                            )
                        except NotImplementedError:
                            sem_llm = None
                            break
                        semantic_attachments.setdefault(rule_id, {})[attachment_id] = sem

                if sem_llm is None:
                    break

        for idx, item in enumerate(agenda_items_full):
            try:
                item_id = str(item.get("item_id") or "")
                pass_b, highlights = _pass_b_for_agenda_item(
                    item=item,
                    rules=rules,
                    evidence_cfg=evidence_cfg,
                    semantic_overrides=semantic_agenda.get(item_id),
                )
                agenda_items_full[idx]["pass_b"] = pass_b
                if idx < len(agenda_items_preview):
                    agenda_items_preview[idx]["pass_b"] = pass_b
                things_you_care_about.extend(highlights)
            except Exception:
                pass_b_failed = True

        # Also surface evidence-backed highlights that appear only in attachments/exhibits.
        # This keeps the UI-ready `things_you_care_about` list evidence-first (E1).
        try:
            things_you_care_about.extend(
                _attachment_highlights_from_rule_results(
                    rule_results=results,
                    existing_highlights=things_you_care_about,
                    semantic_overrides=semantic_attachments if semantic_attachments else None,
                )
            )
        except Exception:
            # Non-fatal: core Pass B output remains.
            pass

    # Persist Pass B artifacts if this run imported a meeting folder.
    if stored_meeting_dir and args.classify_relevance and agenda_items_full:
        try:
            meeting_dir = Path(stored_meeting_dir)
            out_items: List[Dict[str, Any]] = []
            for item in agenda_items_full:
                if item.get("pass_b"):
                    out_items.append(
                        {
                            "item_id": item.get("item_id"),
                            "title": item.get("title"),
                            "pass_b": item.get("pass_b"),
                        }
                    )
            pass_b_path = meeting_dir / "interest_pass_b.json"
            pass_b_path.write_text(json.dumps(out_items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            # Also persist the flattened, UI-ready list (with evidence and links).
            things_path = meeting_dir / "things_you_care_about.json"
            things_path.write_text(
                json.dumps(things_you_care_about, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            meeting_json_path = meeting_dir / "meeting.json"
            if meeting_json_path.exists():
                meeting = json.loads(meeting_json_path.read_text(encoding="utf-8"))
                meeting["interest_pass_b"] = {
                    "stored_path": str(pass_b_path),
                    "count": len(out_items),
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                meeting["things_you_care_about"] = {
                    "stored_path": str(things_path),
                    "count": len(things_you_care_about),
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                meeting_json_path.write_text(json.dumps(meeting, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            # Non-fatal.
            pass

    # D3: Pass C meeting-level summary (heuristic).
    meeting_summary: Optional[Dict[str, Any]] = None
    if args.summarize_meeting:
        meeting_summary = _meeting_pass_c(
            meeting_id=meeting_id,
            agenda_items_full=agenda_items_full,
            things_you_care_about=things_you_care_about,
        )

        if stored_meeting_dir:
            try:
                meeting_dir = Path(stored_meeting_dir)
                pass_c_path = meeting_dir / "meeting_pass_c.json"
                pass_c_path.write_text(json.dumps(meeting_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                meeting_json_path = meeting_dir / "meeting.json"
                if meeting_json_path.exists():
                    meeting = json.loads(meeting_json_path.read_text(encoding="utf-8"))
                    meeting["meeting_pass_c"] = {
                        "stored_path": str(pass_c_path),
                        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    }
                    meeting_json_path.write_text(json.dumps(meeting, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                # Non-fatal.
                pass

    if args.agenda_out:
        agenda_out_path = Path(args.agenda_out)
        agenda_out_path.parent.mkdir(parents=True, exist_ok=True)
        agenda_out_path.write_text(
            json.dumps(agenda_items_full, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    payload = {
        "meeting_id": meeting_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "inputs": {
            "text": str(text_path) if text_path else None,
            "pdf": str(pdf_path) if pdf_path else None,
            "profile": str(profile_path),
            "store_dir": stored_meeting_dir,
        },
        "alert": any_alert,
        "llm_summary_run": llm_summary_run,
        "agenda_items": agenda_items_preview,
        "attachments": attachments_preview,
        "prefilter": prefilter,
        "things_you_care_about": things_you_care_about,
        "meeting_summary": meeting_summary,
        "rule_results": results,
        "source_stats": {k: {"chars": len(v)} for k, v in sources.items()},
        # Store only short previews to avoid giant JSON by default.
        "source_previews": {k: v[:1200] for k, v in sources.items()},
    }

    out_path = Path(args.out) if args.out else Path("out") / f"{meeting_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"Alert: {any_alert}")
    for r in results:
        rid = r.get("rule_id")
        if r.get("alert"):
            print(f"- ALERT {rid} (hits={r.get('hits')})")

    return 2 if (summarize_failed or pass_b_failed) else 0
