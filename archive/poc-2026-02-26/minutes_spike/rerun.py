from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import cli
from .llm import LLMError, ProviderConfig, create_llm_provider
from .profile import ProfileError, load_profile, resolve_profile_path
from .db import (
    DB_FILENAME,
    get_llm_cache,
    put_llm_cache,
    stable_hash_json,
    upsert_meeting_artifact,
)
from .prompts import SUMMARIZE_AGENDA_ITEM_BULLETS


@dataclass(frozen=True)
class RerunResult:
    meeting_dir: Path
    generated_at: str
    ran_pass_a: bool
    ran_pass_b: bool
    ran_pass_c: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_sources_from_meeting_dir(meeting_dir: Path) -> Dict[str, str]:
    """Load stable sources from an imported meeting directory.

    Determinism: prefer stored extracted text artifacts instead of re-extracting from PDF.
    """

    sources: Dict[str, str] = {}
    pdf_text = meeting_dir / "extracted_text.txt"
    txt_text = meeting_dir / "extracted_text_from_txt.txt"

    if pdf_text.exists():
        sources["pdf"] = pdf_text.read_text(encoding="utf-8", errors="replace")
    if txt_text.exists():
        sources["text"] = txt_text.read_text(encoding="utf-8", errors="replace")

    return sources


def _ensure_agenda_items_json(*, meeting_dir: Path, meeting_obj: Dict[str, Any], sources: Dict[str, str]) -> Path:
    """Ensure import-time agenda_items.json exists.

    Some early/legacy meeting folders may include extracted text + meeting.json but
    lack agenda_items.json. Re-running analysis depends on full agenda items.

    Determinism: derive agenda items from the stored extracted text, not by
    re-extracting from PDF.
    """

    agenda_items_path = meeting_dir / "agenda_items.json"
    if agenda_items_path.exists():
        return agenda_items_path

    if not sources:
        raise ValueError("No stored extracted text found; cannot regenerate agenda items")

    # Prefer PDF-extracted canonical text when available.
    preferred_source = "pdf" if "pdf" in sources else next(iter(sources.keys()))
    agenda_text = sources[preferred_source]

    items = cli.extract_agenda_items(agenda_text)
    payload: List[Dict[str, Any]] = [
        {
            "item_id": i.item_id,
            "title": i.title,
            "body_text": i.body_text,
            "start": i.start,
            "end": i.end,
        }
        for i in items
    ]
    _write_json(agenda_items_path, payload)

    # Best-effort: keep meeting.json consistent for UI/back-compat.
    meeting_obj["agenda_items"] = {
        "stored_path": str(agenda_items_path),
        "count": len(payload),
        "source": preferred_source,
        "generated_at": _utc_now_iso(),
        "note": "regenerated",  # small hint for debugging; harmless for readers
    }

    return agenda_items_path


def rerun_meeting(
    *,
    store_dir: Path,
    meeting_id: str,
    profile_path: Optional[str] = None,
    summarize_all_items: bool = True,
    classify_relevance: bool = True,
    summarize_meeting: bool = True,
    llm_provider: Optional[str] = None,
    llm_endpoint: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_timeout_s: Optional[float] = None,
) -> RerunResult:
    """Re-run analysis for a previously imported meeting.

    Overwrites stored analysis artifacts in the meeting folder:
    - agenda_pass_a.json (if summarize_all_items)
    - interest_pass_b.json + things_you_care_about.json (if classify_relevance)
    - meeting_pass_c.json (if summarize_meeting)

    Also updates meeting.json pointers.
    """

    store_dir = store_dir.resolve()
    meeting_dir = (store_dir / meeting_id).resolve()
    if not meeting_dir.exists():
        raise FileNotFoundError(f"Meeting folder not found: {meeting_dir}")

    meeting_json_path = meeting_dir / "meeting.json"
    if not meeting_json_path.exists():
        raise FileNotFoundError(f"meeting.json not found in {meeting_dir}")

    # Load meeting.json early so we can repair missing import-time artifacts.
    meeting_obj = _load_json(meeting_json_path)
    if not isinstance(meeting_obj, dict):
        raise ValueError("meeting.json must be a JSON object")

    sources = _load_sources_from_meeting_dir(meeting_dir)
    if not sources:
        raise ValueError("No stored extracted text found; import the meeting first")

    # Load stored full agenda items (import-time artifact).
    agenda_items_path = _ensure_agenda_items_json(meeting_dir=meeting_dir, meeting_obj=meeting_obj, sources=sources)

    agenda_items_obj = _load_json(agenda_items_path)
    if not isinstance(agenda_items_obj, list):
        raise ValueError("agenda_items.json must be a JSON list")

    agenda_items_full: List[Dict[str, Any]] = []
    for it in agenda_items_obj:
        if not isinstance(it, dict):
            continue
        agenda_items_full.append(it)

    # Resolve and load profile.
    resolved_profile = resolve_profile_path(profile_path, prefer_xdg=False)
    profile = load_profile(resolved_profile)

    llm_profile = profile.get("llm") or {}
    if not isinstance(llm_profile, dict):
        llm_profile = {}

    rules: List[Dict[str, Any]] = profile.get("rules") or []
    evidence_cfg: Dict[str, Any] = (profile.get("output") or {}).get("evidence") or {}

    generated_at = _utc_now_iso()

    # Pass A: per-agenda-item summaries.
    ran_pass_a = False
    if summarize_all_items:
        provider = llm_provider or llm_profile.get("provider") or "ollama"
        endpoint = llm_endpoint or llm_profile.get("endpoint") or "http://localhost:11434"
        model = llm_model or llm_profile.get("model")
        timeout_s = float(llm_timeout_s or llm_profile.get("timeout_s") or 120)

        if not model or not isinstance(model, str) or not model.strip():
            # No model configured; skip Pass A but continue with other steps.
            ran_pass_a = False
        else:
            cfg = ProviderConfig(
                provider=str(provider),
                endpoint=str(endpoint),
                model=str(model).strip(),
                timeout_s=float(timeout_s),
            )
            provider_obj = create_llm_provider(cfg)

            out_items: List[Dict[str, Any]] = []
            # Attach pass_a onto agenda_items_full to feed Pass C.
            for item in agenda_items_full:
                item_id = str(item.get("item_id") or "")
                title = str(item.get("title") or "").strip()
                body_text = str(item.get("body_text") or "").strip()
                body_for_llm = body_text
                if len(body_for_llm) > 12000:
                    body_for_llm = body_for_llm[:12000] + "\n[...truncated...]"

                prompt_template = SUMMARIZE_AGENDA_ITEM_BULLETS
                cache_input = {
                    "kind": "summarize_agenda_item",
                    "title": title,
                    "body_text": body_for_llm,
                    "prompt_id": prompt_template.id,
                    "prompt_version": prompt_template.version,
                    "model": {
                        "provider": str(provider),
                        "endpoint": str(endpoint),
                        "model": str(model).strip(),
                    },
                }
                cache_key = stable_hash_json(cache_input)

                try:
                    cache_hit = False
                    cached = get_llm_cache(db_path=store_dir / DB_FILENAME, cache_key=cache_key)
                    bullets: list[str]
                    if isinstance(cached, dict) and isinstance(cached.get("bullets"), list):
                        bullets = [b for b in cached.get("bullets") if isinstance(b, str) and b.strip()]
                        cache_hit = bool(bullets)
                    else:
                        cache_hit = False
                        bullets = []

                    if not cache_hit:
                        res = provider_obj.summarize_agenda_item(title=title, body_text=body_for_llm)
                        bullets = res.bullets
                        try:
                            put_llm_cache(
                                db_path=store_dir / DB_FILENAME,
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
                    pass_a = {
                        "summary": bullets,
                        "actions": cli._extract_actions_simple(title, body_text),
                        "entities": cli._extract_entities_simple(f"{title}\n{body_text}"),
                        "key_terms": cli._extract_key_terms_simple(title, body_text),
                        "citations": cli._ensure_evidence_citation(body_text, []),
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
                            "cache": {
                                "hit": bool(cache_hit),
                                "key": cache_key,
                            },
                        },
                    }
                    item["pass_a"] = pass_a
                    item["summary"] = bullets
                except LLMError as e:
                    item["pass_a"] = {
                        "summary": [],
                        "actions": [],
                        "entities": [],
                        "key_terms": [],
                        "citations": [],
                        "provenance": {
                            "generated_at": generated_at,
                            "llm": {
                                "provider": str(provider),
                                "endpoint": str(endpoint),
                                "model": str(model).strip(),
                                "timeout_s": float(timeout_s),
                            },
                            "error": e.to_dict(),
                        },
                    }
                    item["summary"] = []
                except Exception:
                    item["pass_a"] = {
                        "summary": [],
                        "actions": [],
                        "entities": [],
                        "key_terms": [],
                        "citations": [],
                        "provenance": {
                            "generated_at": generated_at,
                            "llm": {
                                "provider": str(provider),
                                "endpoint": str(endpoint),
                                "model": str(model).strip() if isinstance(model, str) else None,
                                "timeout_s": float(timeout_s),
                            },
                            "error": {
                                "code": "llm_error",
                                "message": "Unexpected error during summarization",
                            },
                        },
                    }
                    item["summary"] = []

                if item.get("pass_a"):
                    out_items.append({"item_id": item_id, "title": title, "pass_a": item.get("pass_a")})

            summaries_path = meeting_dir / "agenda_pass_a.json"
            _write_json(summaries_path, out_items)

            # I1: mirror Pass A into SQLite.
            try:
                upsert_meeting_artifact(
                    db_path=store_dir / DB_FILENAME,
                    meeting_id=meeting_id,
                    name="agenda_pass_a",
                    obj=out_items,
                )
            except Exception:
                pass

            meeting_obj["agenda_pass_a"] = {
                "stored_path": str(summaries_path),
                "count": len(out_items),
                "generated_at": generated_at,
                "mode": "bullets+heuristics",
                "llm": {
                    "provider": str(provider),
                    "endpoint": str(endpoint),
                    "model": str(model).strip(),
                    "timeout_s": float(timeout_s),
                },
                "profile": str(resolved_profile),
            }
            ran_pass_a = True

    # Pass B: relevance classification.
    ran_pass_b = False
    things_you_care_about: List[Dict[str, Any]] = []
    if classify_relevance:
        # Recompute rule_results against the stored sources, then enrich evidence with agenda/attachment pointers.
        rule_results = [cli.evaluate_rule(rule, sources, evidence_cfg) for rule in rules]

        preferred_source = next((k for k in ("pdf", "text") if k in sources), None)
        agenda_by_source = {k: cli.extract_agenda_items(v) for k, v in sources.items()}
        attachments_by_source = {
            k: cli.extract_attachments(v, agenda_end=max((i.end for i in agenda_by_source.get(k) or []), default=0))
            for k, v in sources.items()
        }
        rule_results = [cli._rule_explanation(r, sources, agenda_by_source, attachments_by_source) for r in rule_results]

        # J1: semantic precision pass (optional; only if an LLM model is configured).
        semantic_agenda: Dict[str, Dict[str, Any]] = {}
        semantic_attachments: Dict[str, Dict[str, Any]] = {}
        sem_llm = None
        sem_generated_at = _utc_now_iso()
        try:
            provider = llm_provider or llm_profile.get("provider") or "ollama"
            endpoint = llm_endpoint or llm_profile.get("endpoint") or "http://localhost:11434"
            model = llm_model or llm_profile.get("model")
            timeout_s = float(llm_timeout_s or llm_profile.get("timeout_s") or 120)
            if isinstance(model, str) and model.strip():
                sem_llm = create_llm_provider(
                    ProviderConfig(
                        provider=str(provider),
                        endpoint=str(endpoint),
                        model=str(model).strip(),
                        timeout_s=float(timeout_s),
                    )
                )
        except Exception:
            sem_llm = None

        if sem_llm is not None and preferred_source is not None:
            prefilter = cli._prefilter_from_rule_results(rule_results)

            rule_cfg_by_id: Dict[str, Dict[str, Any]] = {}
            for r in rules:
                if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("id"):
                    rule_cfg_by_id[str(r.get("id"))] = r

            agenda_by_id: Dict[str, Dict[str, Any]] = {}
            for it in agenda_items_full:
                if isinstance(it, dict) and isinstance(it.get("item_id"), str):
                    agenda_by_id[str(it.get("item_id"))] = it

            attachments_by_id = {a.attachment_id: a for a in (attachments_by_source.get(preferred_source) or [])}

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

                        evidence_snips: List[str] = []
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
                            sem = cli._semantic_classify_relevance(
                                llm=sem_llm,
                            db_path=store_dir / DB_FILENAME,
                            provider=str(provider),
                            endpoint=str(endpoint),
                            model=str(model).strip(),
                            timeout_s=float(timeout_s),
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
                            sem = cli._semantic_classify_relevance(
                                llm=sem_llm,
                            db_path=store_dir / DB_FILENAME,
                            provider=str(provider),
                            endpoint=str(endpoint),
                            model=str(model).strip(),
                            timeout_s=float(timeout_s),
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

        out_items: List[Dict[str, Any]] = []
        for item in agenda_items_full:
            item_id = str(item.get("item_id") or "")
            pass_b, highlights = cli._pass_b_for_agenda_item(
                item=item,
                rules=rules,
                evidence_cfg=evidence_cfg,
                semantic_overrides=semantic_agenda.get(item_id),
            )
            item["pass_b"] = pass_b
            things_you_care_about.extend(highlights)
            out_items.append(
                {
                    "item_id": item.get("item_id"),
                    "title": item.get("title"),
                    "pass_b": pass_b,
                }
            )

        # Also surface attachment-only hits.
        try:
            things_you_care_about.extend(
                cli._attachment_highlights_from_rule_results(
                    rule_results=rule_results,
                    existing_highlights=things_you_care_about,
                    semantic_overrides=semantic_attachments if semantic_attachments else None,
                )
            )
        except Exception:
            pass

        pass_b_path = meeting_dir / "interest_pass_b.json"
        _write_json(pass_b_path, out_items)

        # I1: mirror Pass B into SQLite.
        try:
            upsert_meeting_artifact(
                db_path=store_dir / DB_FILENAME,
                meeting_id=meeting_id,
                name="interest_pass_b",
                obj=out_items,
            )
        except Exception:
            pass

        things_path = meeting_dir / "things_you_care_about.json"
        _write_json(things_path, things_you_care_about)

        # I1: mirror flattened highlights into SQLite.
        try:
            upsert_meeting_artifact(
                db_path=store_dir / DB_FILENAME,
                meeting_id=meeting_id,
                name="things_you_care_about",
                obj=things_you_care_about,
            )
        except Exception:
            pass

        meeting_obj["interest_pass_b"] = {
            "stored_path": str(pass_b_path),
            "count": len(out_items),
            "generated_at": generated_at,
            "profile": str(resolved_profile),
        }
        meeting_obj["things_you_care_about"] = {
            "stored_path": str(things_path),
            "count": len(things_you_care_about),
            "generated_at": generated_at,
            "profile": str(resolved_profile),
        }
        ran_pass_b = True

    # Pass C: meeting-level summary.
    ran_pass_c = False
    if summarize_meeting:
        meeting_summary = cli._meeting_pass_c(
            meeting_id=meeting_id,
            agenda_items_full=agenda_items_full,
            things_you_care_about=things_you_care_about,
        )
        pass_c_path = meeting_dir / "meeting_pass_c.json"
        _write_json(pass_c_path, meeting_summary)

        # I1: mirror Pass C into SQLite.
        try:
            upsert_meeting_artifact(
                db_path=store_dir / DB_FILENAME,
                meeting_id=meeting_id,
                name="meeting_pass_c",
                obj=meeting_summary,
            )
        except Exception:
            pass
        meeting_obj["meeting_pass_c"] = {
            "stored_path": str(pass_c_path),
            "generated_at": generated_at,
            "profile": str(resolved_profile),
        }
        ran_pass_c = True

    # Always ensure meeting.json knows where agenda_items are.
    meeting_obj["agenda_items"] = {
        "stored_path": str(agenda_items_path),
        "count": len(agenda_items_full),
        "source": (
            (meeting_obj.get("agenda_items", {}) or {}).get("source")
            if isinstance(meeting_obj.get("agenda_items"), dict)
            else None
        ),
    }

    _write_json(meeting_json_path, meeting_obj)

    return RerunResult(
        meeting_dir=meeting_dir,
        generated_at=generated_at,
        ran_pass_a=ran_pass_a,
        ran_pass_b=ran_pass_b,
        ran_pass_c=ran_pass_c,
    )
