from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import asdict
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .chat import answer_question
from .db import (
    DB_FILENAME,
    get_meeting,
    get_meeting_artifact,
    list_meeting_artifact_names,
    list_meetings,
    meeting_artifact_exists,
    upsert_meeting,
    upsert_meeting_artifact,
)
from .rerun import rerun_meeting
from .store import IngestionError, import_meeting
from .metadata import extract_meeting_metadata


_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _guess_meeting_date(meeting_id: str) -> Optional[str]:
    m = _DATE_RE.search(meeting_id or "")
    return m.group(0) if m else None


def _safe_meeting_dir(*, store_dir: Path, meeting_id: str) -> Optional[Path]:
    """Resolve store_dir/meeting_id while preventing path traversal."""

    meeting_id = (meeting_id or "").strip()
    if not meeting_id:
        return None
    # Reject anything that looks like a path.
    if "/" in meeting_id or "\\" in meeting_id:
        return None
    if meeting_id in {".", ".."}:
        return None

    try:
        store_dir = store_dir.resolve()
    except Exception:
        pass
    try:
        meeting_dir = (store_dir / meeting_id).resolve()
    except Exception:
        meeting_dir = store_dir / meeting_id

    try:
        # Ensure meeting_dir is within store_dir.
        meeting_dir.relative_to(store_dir)
    except Exception:
        return None

    return meeting_dir


def validate_store_dir(*, store_dir: Path) -> tuple[Path, Optional[str]]:
    """Resolve and validate the store directory for local persistence.

    Returns (resolved_store_dir, error_message_or_None).
    """

    try:
        resolved = store_dir.expanduser().resolve()
    except Exception:
        resolved = store_dir

    # Must be a directory path (existing or creatable).
    if resolved.exists() and not resolved.is_dir():
        return resolved, f"Store path is not a directory: {resolved}"

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return resolved, f"Store directory is not usable: {resolved} ({type(e).__name__}: {e})"

    # Must be writable (create/delete a tiny probe file).
    probe = resolved / f".councilsense_write_probe_{os.getpid()}_{time.time_ns()}"
    try:
        probe.write_bytes(b"")
        probe.unlink(missing_ok=True)
    except Exception as e:
        try:
            probe.unlink(missing_ok=True)
        except Exception:
            pass
        return resolved, f"Store directory is not writable: {resolved} ({type(e).__name__}: {e})"

    return resolved, None


def sync_store_dir_to_db(*, store_dir: Path) -> Path:
    """Best-effort indexer: scan meeting folders and upsert into SQLite.

    This allows older imported meetings (folders on disk) to appear in the meeting list.
    """

    store_dir, err = validate_store_dir(store_dir=store_dir)
    if err:
        # Caller should render a clear error; return the expected DB path anyway.
        return store_dir / DB_FILENAME
    db_path = store_dir / DB_FILENAME

    for child in store_dir.iterdir() if store_dir.exists() else []:
        if not child.is_dir():
            continue
        ingestion_path = child / "ingestion.json"
        if not ingestion_path.exists():
            continue

        try:
            ingestion = json.loads(ingestion_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        meeting_id = str(ingestion.get("meeting_id") or child.name)
        imported_at = str(ingestion.get("imported_at") or "")
        if not imported_at:
            continue

        inputs = ingestion.get("inputs") or {}
        if not isinstance(inputs, dict):
            inputs = {}

        pdf_orig = None
        text_orig = None
        if isinstance(inputs.get("pdf"), dict):
            pdf_orig = inputs["pdf"].get("original_path")
        if isinstance(inputs.get("text"), dict):
            text_orig = inputs["text"].get("original_path")

        title = None
        if pdf_orig:
            try:
                title = Path(str(pdf_orig)).name
            except Exception:
                title = str(pdf_orig)
        elif text_orig:
            try:
                title = Path(str(text_orig)).name
            except Exception:
                title = str(text_orig)

        upsert_meeting(
            db_path=db_path,
            meeting_id=meeting_id,
            imported_at=imported_at,
            meeting_dir=child,
            meeting_date=None,
            meeting_location=None,
            title=title,
            source_pdf_path=(str(pdf_orig) if pdf_orig else None),
            source_text_path=(str(text_orig) if text_orig else None),
        )

        # L1: best-effort metadata extraction. Prefer stored meeting.json fields, else scan extracted text.
        meeting_date: Optional[str] = None
        meeting_location: Optional[str] = None
        try:
            meeting_json_path = child / "meeting.json"
            if meeting_json_path.exists():
                meeting_obj = json.loads(meeting_json_path.read_text(encoding="utf-8"))
            else:
                meeting_obj = None
        except Exception:
            meeting_obj = None

        if isinstance(meeting_obj, dict):
            d = meeting_obj.get("meeting_date")
            loc = meeting_obj.get("meeting_location")
            meeting_date = str(d) if d else None
            meeting_location = str(loc) if loc else None

        if meeting_date is None or meeting_location is None:
            try:
                p = child / "extracted_text.txt"
                if not p.exists():
                    p = child / "extracted_text_from_txt.txt"
                if p.exists():
                    head = p.read_text(encoding="utf-8", errors="replace")
                    d2, loc2 = extract_meeting_metadata(head)
                    if meeting_date is None:
                        meeting_date = d2
                    if meeting_location is None:
                        meeting_location = loc2
            except Exception:
                pass

        if meeting_date is None:
            meeting_date = _guess_meeting_date(meeting_id)

        try:
            upsert_meeting(
                db_path=db_path,
                meeting_id=meeting_id,
                imported_at=imported_at,
                meeting_dir=child,
                meeting_date=meeting_date,
                meeting_location=meeting_location,
                title=title,
                source_pdf_path=(str(pdf_orig) if pdf_orig else None),
                source_text_path=(str(text_orig) if text_orig else None),
            )
        except Exception:
            pass

        # I1: mirror known artifacts into SQLite (best-effort).
        for name, filename in (
            ("agenda_items", "agenda_items.json"),
            ("attachments", "attachments.json"),
            ("agenda_pass_a", "agenda_pass_a.json"),
            ("interest_pass_b", "interest_pass_b.json"),
            ("things_you_care_about", "things_you_care_about.json"),
            ("meeting_pass_c", "meeting_pass_c.json"),
        ):
            try:
                if meeting_artifact_exists(db_path=db_path, meeting_id=meeting_id, name=name):
                    continue
                p = child / filename
                if not p.exists():
                    continue
                obj = json.loads(p.read_text(encoding="utf-8"))
                upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name=name, obj=obj)
            except Exception:
                continue

    return db_path


def render_meeting_list_html(*, store_dir: Path) -> str:
    store_dir, err = validate_store_dir(store_dir=store_dir)
    if err:
        return (
            "<!doctype html>"
            "<html><head>"
            "<meta charset=\"utf-8\"/>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "<title>CouncilSense — Store error</title>"
            "</head><body style=\"font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;margin:24px;\">"
            "<h1>Store directory error</h1>"
            f"<p><strong>Store:</strong> <code>{escape(str(store_dir))}</code></p>"
            f"<p>{escape(err)}</p>"
            "<p>Fix: restart the server with a valid <code>--store-dir</code> or adjust permissions.</p>"
            "</body></html>"
        )

    db_path = sync_store_dir_to_db(store_dir=store_dir)
    meetings = list_meetings(db_path=db_path)

    def _load_json(path: Path) -> Optional[object]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _analysis_badges(*, meeting_id: str, meeting_dir: Path) -> list[str]:
        """Best-effort: infer which analysis artifacts exist for a meeting.

        Prefer DB (I1); fall back to meeting.json pointers for back-compat.
        """

        badges: list[str] = []

        try:
            if meeting_artifact_exists(db_path=db_path, meeting_id=meeting_id, name="agenda_pass_a"):
                badges.append("Pass A")
            if meeting_artifact_exists(db_path=db_path, meeting_id=meeting_id, name="things_you_care_about") or meeting_artifact_exists(
                db_path=db_path, meeting_id=meeting_id, name="interest_pass_b"
            ):
                badges.append("Pass B")
            if meeting_artifact_exists(db_path=db_path, meeting_id=meeting_id, name="meeting_pass_c"):
                badges.append("Pass C")
            if badges:
                return badges
        except Exception:
            pass

        meeting_json_path = meeting_dir / "meeting.json"
        if not meeting_json_path.exists():
            return []
        obj = _load_json(meeting_json_path)
        if not isinstance(obj, dict):
            return []

        def has_artifact(key: str) -> bool:
            val = obj.get(key)
            if not isinstance(val, dict):
                return False
            sp = val.get("stored_path")
            if not isinstance(sp, str) or not sp:
                return False
            try:
                return Path(sp).exists()
            except Exception:
                return False

        if has_artifact("agenda_pass_a"):
            badges.append("Pass A")
        if has_artifact("things_you_care_about") or has_artifact("interest_pass_b"):
            badges.append("Pass B")
        if has_artifact("meeting_pass_c"):
            badges.append("Pass C")

        return badges

    rows = []
    for m in meetings:
        display_title = m.title or m.meeting_id
        display_date = m.meeting_date or ""

        badges = _analysis_badges(meeting_id=m.meeting_id, meeting_dir=Path(m.meeting_dir))
        badge_html = "".join(f"<span class=\"badge\">{escape(b)}</span>" for b in badges)

        rows.append(
            "<tr>"
            f"<td>{escape(display_date)}</td>"
            f"<td><a href=\"/meetings/{escape(m.meeting_id)}\">{escape(display_title)}</a> {badge_html}</td>"
            f"<td><code>{escape(m.imported_at)}</code></td>"
            "</tr>"
        )

    body = "\n".join(rows) if rows else "<tr><td colspan=\"3\">No meetings imported yet.</td></tr>"

    upload_html = (
        "<h2 style=\"margin-top:28px\">Import a meeting packet</h2>"
        "<form method=\"post\" action=\"/import\" enctype=\"multipart/form-data\">"
        "<p><label>PDF packet: <input type=\"file\" name=\"pdf\" accept=\"application/pdf,.pdf\" required/></label></p>"
        "<p><label>Text minutes (optional): <input type=\"file\" name=\"text\" accept=\"text/plain,.txt\"/></label></p>"
        "<p><button type=\"submit\">Upload &amp; import</button></p>"
        "<p><small>Tip: scanned PDFs will fail (OCR not supported yet).</small></p>"
        "</form>"
    )

    return (
        "<!doctype html>"
        "<html><head>"
        "<meta charset=\"utf-8\"/>"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        "<title>CouncilSense — Meetings</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;margin:24px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border-bottom:1px solid #ddd;padding:10px;text-align:left;vertical-align:top;}"
        "th{background:#fafafa;}"
        "code{font-size:0.9em;}"
        "button{padding:8px 14px;border:1px solid #ddd;border-radius:10px;background:#fafafa;cursor:pointer;}"
        "button:hover{background:#f0f0f0;}"
        ".badge{display:inline-block;margin-left:6px;padding:2px 8px;border:1px solid #ddd;border-radius:999px;font-size:12px;color:#444;background:#f7f7f7;}"
        "</style>"
        "</head><body>"
        "<h1>Meetings</h1>"
        f"<p><small>Store: {escape(str(store_dir.resolve()))}</small></p>"
        "<table>"
        "<thead><tr><th>Date</th><th>Meeting</th><th>Imported (UTC)</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        + upload_html
        + "</body></html>"
    )


def render_meeting_detail_html(*, store_dir: Path, meeting_id: str) -> str:
    store_dir, err = validate_store_dir(store_dir=store_dir)
    if err:
        return (
            "<!doctype html>"
            "<html><head><meta charset=\"utf-8\"/>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "<title>CouncilSense — Store error</title></head>"
            "<body style=\"font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;margin:24px;\">"
            "<p><a href=\"/\">← Back</a></p>"
            "<h1>Store directory error</h1>"
            f"<p><strong>Store:</strong> <code>{escape(str(store_dir))}</code></p>"
            f"<p>{escape(err)}</p>"
            "</body></html>"
        )

    db_path = sync_store_dir_to_db(store_dir=store_dir)
    meeting = get_meeting(db_path=db_path, meeting_id=meeting_id)

    if meeting is None:
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\"/>"
            "<title>Meeting not found</title></head><body>"
            "<p><a href=\"/\">← Back</a></p>"
            "<h1>Meeting not found</h1>"
            "</body></html>"
        )

    meeting_dir = Path(meeting.meeting_dir)
    meeting_json_path = meeting_dir / "meeting.json"
    ingestion_json_path = meeting_dir / "ingestion.json"

    def _load_json(path: Path) -> Optional[object]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # Conventional artifact filenames within the meeting folder.
    agenda_items_path = meeting_dir / "agenda_items.json"
    attachments_path = meeting_dir / "attachments.json"
    agenda_pass_a_path = meeting_dir / "agenda_pass_a.json"
    interest_pass_b_path = meeting_dir / "interest_pass_b.json"
    things_path = meeting_dir / "things_you_care_about.json"
    meeting_pass_c_path = meeting_dir / "meeting_pass_c.json"

    # I1: Prefer artifacts from SQLite.
    agenda_items = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="agenda_items")
    if not isinstance(agenda_items, list):
        agenda_items = []

    pass_a_items = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="agenda_pass_a")
    if not isinstance(pass_a_items, list):
        pass_a_items = []
    pass_a_by_id = {}
    for it in pass_a_items:
        if isinstance(it, dict) and it.get("item_id"):
            pass_a_by_id[str(it.get("item_id"))] = it

    things_you_care_about = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="things_you_care_about")
    if not isinstance(things_you_care_about, list):
        things_you_care_about = []

    meeting_pass_c = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="meeting_pass_c")
    if not isinstance(meeting_pass_c, dict):
        meeting_pass_c = {}

    # If DB isn't populated yet, fall back to the on-disk JSON artifacts.
    if not agenda_items and agenda_items_path.exists():
        obj = _load_json(agenda_items_path)
        if isinstance(obj, list):
            agenda_items = obj
            try:
                upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="agenda_items", obj=obj)
            except Exception:
                pass

    if not pass_a_items and agenda_pass_a_path.exists():
        obj = _load_json(agenda_pass_a_path)
        if isinstance(obj, list):
            pass_a_items = obj
            try:
                upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="agenda_pass_a", obj=obj)
            except Exception:
                pass

    if not things_you_care_about and things_path.exists():
        obj = _load_json(things_path)
        if isinstance(obj, list):
            things_you_care_about = obj
            try:
                upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="things_you_care_about", obj=obj)
            except Exception:
                pass

    if not meeting_pass_c and meeting_pass_c_path.exists():
        obj = _load_json(meeting_pass_c_path)
        if isinstance(obj, dict):
            meeting_pass_c = obj
            try:
                upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="meeting_pass_c", obj=obj)
            except Exception:
                pass

    # Back-compat: derive a minimal highlights list from interest_pass_b if things list wasn't stored.
    if not things_you_care_about:
        pb = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="interest_pass_b")
        if pb is None and interest_pass_b_path.exists():
            pb = _load_json(interest_pass_b_path)
            if pb is not None:
                try:
                    upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name="interest_pass_b", obj=pb)
                except Exception:
                    pass
        if isinstance(pb, list):
            derived = []
            for item in pb:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("item_id") or "")
                title = str(item.get("title") or "")
                pass_b = item.get("pass_b")
                if not isinstance(pass_b, dict):
                    continue
                for rule_id, rr in pass_b.items():
                    if not isinstance(rr, dict):
                        continue
                    if not rr.get("relevant"):
                        continue
                    ev = rr.get("evidence")
                    if not isinstance(ev, list) or not ev:
                        continue
                    derived.append(
                        {
                            "title": f"{item_id}: {title}" if item_id else title,
                            "category": str(rule_id),
                            "why": rr.get("why"),
                            "confidence": rr.get("confidence"),
                            "evidence": ev,
                            "links": {"agenda_item": {"item_id": item_id, "title": title}},
                        }
                    )
            things_you_care_about = derived

    # Normalize meeting_pass_c to a dict for downstream rendering.
    if not isinstance(meeting_pass_c, dict):
        meeting_pass_c = {}

    links = []
    for filename in (
        "meeting.json",
        "ingestion.json",
        "agenda_items.json",
        "attachments.json",
        "agenda_pass_a.json",
        "interest_pass_b.json",
        "things_you_care_about.json",
        "meeting_pass_c.json",
        "extracted_text.txt",
        "extracted_text_from_txt.txt",
    ):
        try:
            p = meeting_dir / filename
            if p.exists():
                links.append(f"<li><a href=\"/raw/{escape(meeting.meeting_id)}/{escape(filename)}\">{escape(filename)}</a></li>")
        except Exception:
            continue

    title = meeting.title or meeting.meeting_id
    date = meeting.meeting_date or ""

    chat_html = (
        "<h2>Chat (this meeting)</h2>"
        "<p><small>Evidence-first: answers include quotes or say <em>not found</em>.</small></p>"
        "<form id=\"chatForm\">"
        "<p><input id=\"chatQ\" type=\"text\" size=\"80\" placeholder=\"Ask a question (e.g., Why was Sunset Flats mentioned?)\"/></p>"
        "<p><button type=\"submit\">Ask</button></p>"
        "</form>"
        "<div id=\"chatOut\" style=\"padding:12px;border:1px solid #e5e5e5;border-radius:10px;\"></div>"
        "<script>"
        "(function(){"
        "var form=document.getElementById('chatForm');"
        "var q=document.getElementById('chatQ');"
        "var out=document.getElementById('chatOut');"
        "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;','\'':'&#39;'}[c]);});}"
        "function render(resp){"
        "var html='';"
        "html+='<div><strong>Answer:</strong> '+esc(resp.answer||'')+'</div>';"
        "if(resp.evidence&&resp.evidence.length){"
        "html+='<div style=\"margin-top:10px\"><strong>Evidence</strong><ul>';"
        "for(var i=0;i<resp.evidence.length;i++){"
        "var ev=resp.evidence[i]||{};"
        "var meta='';"
        "var link='';"
        "if(ev.bucket==='attachment' && ev.attachment){"
        "var a=ev.attachment||{};"
        "meta='Attachment: '+(a.title||a.attachment_id||'');"
        "if(a.type_guess){meta+=' ('+a.type_guess+')';}"
        "link='/raw/" + escape(meeting.meeting_id) + "/attachments.json';"
        "} else if(ev.bucket==='agenda_item' && ev.agenda_item){"
        "var it=ev.agenda_item||{};"
        "meta='Agenda: '+(it.item_id||'');"
        "if(it.title){meta+=' — '+it.title;}"
        "link='/raw/" + escape(meeting.meeting_id) + "/agenda_items.json';"
        "} else if(ev.bucket){"
        "meta=ev.bucket;"
        "if(ev.bucket==='meeting_text'){link='/raw/" + escape(meeting.meeting_id) + "/extracted_text.txt';}"
        "}"
        "var metaHtml='<code>'+esc(meta)+'</code>';"
        "if(link){metaHtml+=' <a href=\"'+esc(link)+'\" target=\"_blank\" rel=\"noopener\">raw</a>';"
        "if(ev.bucket==='meeting_text'){"
        "metaHtml+=' <a href=\"/raw/" + escape(meeting.meeting_id) + "/extracted_text_from_txt.txt\" target=\"_blank\" rel=\"noopener\">raw(txt)</a>';"
        "}"
        "}"
        "html+='<li style=\"margin-bottom:10px\"><div>'+metaHtml+'</div><div style=\"margin-top:4px\">'+esc(ev.snippet||'')+'</div></li>';"
        "}"
        "html+='</ul></div>';"
        "}"
        "out.innerHTML=html;"
        "}"
        "form.addEventListener('submit', function(e){"
        "e.preventDefault();"
        "var question=(q.value||'').trim();"
        "if(!question){out.innerHTML='<em>Type a question first.</em>';return;}"
        "out.innerHTML='<em>Thinking…</em>';"
        "fetch('/api/meetings/" + escape(meeting.meeting_id) + "/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question: question})})"
        ".then(function(r){return r.json();})"
        ".then(render)"
        ".catch(function(err){out.innerHTML='<em>Chat error: '+esc(err)+'</em>';});"
        "});"
        "})();"
        "</script>"
    )

    # Meeting summary section.
    meeting_summary_html = ""
    if meeting_pass_c:
        highlights = meeting_pass_c.get("highlights")
        if not isinstance(highlights, list):
            highlights = []
        hl_rows = []
        for h in highlights:
            if not isinstance(h, dict):
                continue
            h_title = str(h.get("title") or "")
            why = str(h.get("why") or "")
            ev = h.get("evidence")
            ev_snip = ""
            if isinstance(ev, list) and ev:
                first = ev[0]
                if isinstance(first, dict):
                    sn = first.get("snippet")
                    if isinstance(sn, str):
                        ev_snip = sn
            if not (h_title or why):
                continue
            hl_rows.append(
                "<li>"
                f"<strong>{escape(h_title)}</strong><br/>"
                f"{escape(why)}"
                + (f"<div style=\"margin-top:6px;color:#444\"><em>Evidence:</em> {escape(ev_snip)}</div>" if ev_snip else "")
                + "</li>"
            )

        ordinances = meeting_pass_c.get("ordinances_resolutions")
        if not isinstance(ordinances, list):
            ordinances = []
        ord_rows = []
        for o in ordinances:
            if not isinstance(o, dict):
                continue
            kind = str(o.get("kind") or "")
            item_id = str(o.get("item_id") or "")
            o_title = str(o.get("title") or "")
            if not o_title:
                continue
            ord_rows.append(f"<li>{escape(kind)} — <strong>{escape(item_id)}</strong> {escape(o_title)}</li>")

        watch = meeting_pass_c.get("watchlist_hits")
        if not isinstance(watch, list):
            watch = []
        watch_rows = []
        for w in watch:
            if not isinstance(w, dict):
                continue
            cat = w.get("category")
            cnt = w.get("count")
            if isinstance(cat, str) and cat:
                watch_rows.append(f"<li>{escape(cat)}: {escape(str(cnt))}</li>")

        meeting_summary_html = (
            "<h2>Meeting summary</h2>"
            + ("<h3>Highlights</h3><ul>" + "".join(hl_rows) + "</ul>" if hl_rows else "<p>(No summary highlights yet.)</p>")
            + ("<h3>Ordinances / resolutions</h3><ul>" + "".join(ord_rows) + "</ul>" if ord_rows else "")
            + ("<h3>Watchlist hits</h3><ul>" + "".join(watch_rows) + "</ul>" if watch_rows else "")
        )
    else:
        meeting_summary_html = (
            "<h2>Meeting summary</h2>"
            "<p>(No meeting-level summary stored yet.)</p>"
        )

    # Things you care about section.
    tyca_rows = []
    for h in things_you_care_about:
        if not isinstance(h, dict):
            continue
        h_title = str(h.get("title") or "")
        why = str(h.get("why") or "")
        category = str(h.get("category") or "")
        evidence = h.get("evidence")
        ev_bits = []
        if isinstance(evidence, list):
            for ev in evidence[:3]:
                if not isinstance(ev, dict):
                    continue
                sn = ev.get("snippet")
                if isinstance(sn, str) and sn.strip():
                    ev_bits.append(f"<li><code>Evidence</code> {escape(sn.strip())}</li>")
        if not (h_title or why or ev_bits):
            continue
        tyca_rows.append(
            "<li style=\"margin-bottom:14px\">"
            + (f"<strong>{escape(h_title)}</strong>" if h_title else "<strong>(untitled)</strong>")
            + (f" <span style=\"color:#666\">[{escape(category)}]</span>" if category else "")
            + (f"<div style=\"margin-top:6px\">{escape(why)}</div>" if why else "")
            + ("<ul style=\"margin-top:6px\">" + "".join(ev_bits) + "</ul>" if ev_bits else "")
            + "</li>"
        )

    things_html = (
        "<h2>Things you care about</h2>"
        + ("<ul>" + "".join(tyca_rows) + "</ul>" if tyca_rows else "<p>(No interest highlights stored yet.)</p>")
    )

    # Agenda items section.
    agenda_rows = []
    for item in agenda_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "")
        item_title = str(item.get("title") or "")
        pass_a = pass_a_by_id.get(item_id, {})
        pass_a_obj = pass_a.get("pass_a") if isinstance(pass_a, dict) else None
        if not isinstance(pass_a_obj, dict):
            pass_a_obj = {}
        bullets = pass_a_obj.get("summary")
        if not isinstance(bullets, list):
            bullets = []
        citations = pass_a_obj.get("citations")
        if not isinstance(citations, list):
            citations = []

        b_html = "".join(f"<li>{escape(str(b))}</li>" for b in bullets if isinstance(b, str) and b.strip())
        c_html = "".join(
            f"<li>{escape(str(c))}</li>" for c in citations[:2] if isinstance(c, str) and c.strip()
        )

        agenda_rows.append(
            "<div style=\"padding:12px;border:1px solid #e5e5e5;border-radius:10px;margin:12px 0\">"
            f"<h3 style=\"margin:0 0 8px 0\">{escape(item_id)} — {escape(item_title)}</h3>"
            + ("<strong>Summary</strong><ul>" + b_html + "</ul>" if b_html else "<p><em>(No per-item summary stored yet.)</em></p>")
            + ("<strong>Evidence</strong><ul>" + c_html + "</ul>" if c_html else "")
            + "</div>"
        )

    agenda_html = (
        "<h2>Agenda items</h2>"
        + ("".join(agenda_rows) if agenda_rows else "<p>(No agenda items detected.)</p>")
    )

    return (
        "<!doctype html>"
        "<html><head>"
        "<meta charset=\"utf-8\"/>"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        f"<title>CouncilSense — {escape(title)}</title>"
        "<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;margin:24px;}"
        "code{font-size:0.9em;}"
        "h2{margin-top:28px;}"
        "</style>"
        "</head><body>"
        "<p><a href=\"/\">← Back to meetings</a></p>"
        f"<h1>{escape(title)}</h1>"
        f"<p>Date: <strong>{escape(date)}</strong></p>"
        f"<p>Imported (UTC): <code>{escape(meeting.imported_at)}</code></p>"
        + chat_html
        + "<h2>Artifacts</h2>"
        f"<ul>{''.join(links) if links else '<li>(none)</li>'}</ul>"
        "<h2>Re-run analysis</h2>"
        "<form method=\"post\" action=\"/meetings/"
        + escape(meeting.meeting_id)
        + "/rerun\">"
        "<p><label>Profile path (optional): <input type=\"text\" name=\"profile\" size=\"60\" placeholder=\"./interest_profile.yaml\"/></label></p>"
        "<p>"
        "<label><input type=\"checkbox\" name=\"summarize_all_items\" value=\"1\"/> Summarize agenda items (Pass A; requires LLM config)</label><br/>"
        "<label><input type=\"checkbox\" name=\"classify_relevance\" value=\"1\" checked/> Classify relevance (Pass B)</label><br/>"
        "<label><input type=\"checkbox\" name=\"summarize_meeting\" value=\"1\" checked/> Meeting-level summary (Pass C)</label>"
        "</p>"
        "<p><button type=\"submit\">Re-run analysis</button></p>"
        "</form>"
        + meeting_summary_html
        + things_html
        + agenda_html
        + "<hr/>"
        + "<p><small>Tip: to populate summaries and highlights, re-run with flags like "
        + "<code>--summarize-all-items</code>, <code>--classify-relevance</code>, and <code>--summarize-meeting</code> "
        + "using the same <code>--store-dir</code>.</small></p>"
        "</body></html>"
    )


class _Handler(BaseHTTPRequestHandler):
    server_version = "CouncilSenseHTTP/0.1"

    @staticmethod
    def _parse_multipart_form_data(
        *,
        body: bytes,
        content_type: str,
    ) -> dict[str, dict[str, object]]:
        """Parse multipart/form-data into a dict keyed by field name.

        Minimal parser intended for local-only uploads. Supports file parts and
        regular text fields. For file parts, returns:

        {"filename": str|None, "content_type": str|None, "data": bytes}
        """

        # Extract boundary.
        m = re.search(r"boundary=([^;]+)", content_type)
        if not m:
            raise ValueError("Missing multipart boundary")
        boundary = m.group(1).strip()
        if boundary.startswith('"') and boundary.endswith('"') and len(boundary) >= 2:
            boundary = boundary[1:-1]
        if not boundary:
            raise ValueError("Empty multipart boundary")

        b = boundary.encode("utf-8", errors="replace")
        marker = b"--" + b

        parts = body.split(marker)
        out: dict[str, dict[str, object]] = {}

        for p in parts:
            # Each part is prefixed by CRLF; the last part ends with '--'.
            if p.startswith(b"\r\n"):
                p = p[2:]
            elif p.startswith(b"\n"):
                p = p[1:]

            # Parts may end with a newline before the next boundary marker.
            # Avoid generic .strip() here: it can corrupt binary uploads.
            if p.endswith(b"\r\n"):
                p = p[:-2]
            elif p.endswith(b"\n"):
                p = p[:-1]

            if not p or p == b"--":
                continue

            # Trim trailing end marker.
            if p.endswith(b"--"):
                p = p[:-2].strip()

            # Split headers/body.
            sep = b"\r\n\r\n"
            if sep in p:
                header_blob, data = p.split(sep, 1)
                header_lines = header_blob.split(b"\r\n")
                # Body often ends with CRLF; trim one.
                if data.endswith(b"\r\n"):
                    data = data[:-2]
            else:
                sep2 = b"\n\n"
                if sep2 not in p:
                    continue
                header_blob, data = p.split(sep2, 1)
                header_lines = header_blob.split(b"\n")
                if data.endswith(b"\n"):
                    data = data[:-1]

            headers: dict[str, str] = {}
            for raw in header_lines:
                try:
                    line = raw.decode("latin-1", errors="replace")
                except Exception:
                    continue
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

            cd = headers.get("content-disposition") or ""
            name_m = re.search(r"\bname=\"([^\"]+)\"", cd)
            if not name_m:
                name_m = re.search(r"\bname=([^;]+)", cd)
            if not name_m:
                continue
            field_name = name_m.group(1).strip().strip('"')
            if not field_name:
                continue

            filename = None
            fn_m = re.search(r"\bfilename=\"([^\"]*)\"", cd)
            if not fn_m:
                fn_m = re.search(r"\bfilename=([^;]+)", cd)
            if fn_m is not None:
                filename = fn_m.group(1).strip().strip('"') or None

            out[field_name] = {
                "filename": filename,
                "content_type": headers.get("content-type"),
                "data": data,
            }

        return out

    def _render_error_page(self, *, title: str, message: str, status: int = 400) -> None:
        html = (
            "<!doctype html><html><head><meta charset=\"utf-8\"/>"
            f"<title>{escape(title)}</title>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "</head><body style=\"font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;margin:24px;\">"
            "<p><a href=\"/\">← Back</a></p>"
            f"<h1>{escape(title)}</h1>"
            f"<p>{escape(message)}</p>"
            "</body></html>"
        )
        self._send(status, html.encode("utf-8"), content_type="text/html; charset=utf-8")

    def _send_json(self, status: int, obj: object) -> None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, payload, content_type="application/json; charset=utf-8")

    def _send_json_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": str(message)})

    def _read_json_body(self) -> object:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except Exception:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(body.decode("utf-8", errors="replace") or "null")
        except Exception:
            raise ValueError("Invalid JSON")

    def _store_dir_or_error(self) -> Optional[Path]:
        store_dir: Path = self.server.store_dir  # type: ignore[attr-defined]
        store_dir, err = validate_store_dir(store_dir=store_dir)
        if err:
            self._render_error_page(title="Store directory error", message=err, status=500)
            return None
        return store_dir

    def _store_dir_or_json_error(self) -> Optional[Path]:
        store_dir: Path = self.server.store_dir  # type: ignore[attr-defined]
        store_dir, err = validate_store_dir(store_dir=store_dir)
        if err:
            self._send_json_error(500, err)
            return None
        return store_dir

    def _api_meeting_list(self, *, store_dir: Path) -> None:
        db_path = sync_store_dir_to_db(store_dir=store_dir)
        meetings = list_meetings(db_path=db_path)
        out: list[dict[str, object]] = []
        for m in meetings:
            # Best-effort flags for UI badges.
            try:
                has_pass_a = meeting_artifact_exists(db_path=db_path, meeting_id=m.meeting_id, name="agenda_pass_a")
                has_pass_b = meeting_artifact_exists(db_path=db_path, meeting_id=m.meeting_id, name="things_you_care_about") or meeting_artifact_exists(
                    db_path=db_path, meeting_id=m.meeting_id, name="interest_pass_b"
                )
                has_pass_c = meeting_artifact_exists(db_path=db_path, meeting_id=m.meeting_id, name="meeting_pass_c")
            except Exception:
                has_pass_a = False
                has_pass_b = False
                has_pass_c = False

            # Back-compat: if artifacts aren't mirrored yet, infer from disk.
            try:
                meeting_dir = Path(m.meeting_dir)
                if not has_pass_a:
                    has_pass_a = (meeting_dir / "agenda_pass_a.json").exists()
                if not has_pass_b:
                    has_pass_b = (meeting_dir / "things_you_care_about.json").exists() or (meeting_dir / "interest_pass_b.json").exists()
                if not has_pass_c:
                    has_pass_c = (meeting_dir / "meeting_pass_c.json").exists()
            except Exception:
                pass

            out.append(
                {
                    "meeting_id": m.meeting_id,
                    "imported_at": m.imported_at,
                    "meeting_date": m.meeting_date,
                    "meeting_location": getattr(m, "meeting_location", None),
                    "title": m.title,
                    "source_pdf_path": m.source_pdf_path,
                    "source_text_path": m.source_text_path,
                    "badges": {
                        "pass_a": bool(has_pass_a),
                        "pass_b": bool(has_pass_b),
                        "pass_c": bool(has_pass_c),
                    },
                }
            )
        self._send_json(200, {"meetings": out})

    def _api_meeting_detail(self, *, store_dir: Path, meeting_id: str) -> None:
        db_path = sync_store_dir_to_db(store_dir=store_dir)
        row = get_meeting(db_path=db_path, meeting_id=meeting_id)
        if row is None:
            # Fallback: if the DB index is stale/missing (or ingestion.json was missing),
            # attempt to load a meeting directly from the on-disk folder.
            meeting_dir = _safe_meeting_dir(store_dir=store_dir, meeting_id=meeting_id)
            if meeting_dir is None or not meeting_dir.exists():
                self._send_json_error(404, "Not found")
                return

            meeting_json_path = meeting_dir / "meeting.json"
            if not meeting_json_path.exists():
                self._send_json_error(404, "Not found")
                return

            imported_at = ""
            title = None
            source_pdf_path = None
            source_text_path = None

            ingestion_path = meeting_dir / "ingestion.json"
            if ingestion_path.exists():
                try:
                    ingestion = json.loads(ingestion_path.read_text(encoding="utf-8"))
                except Exception:
                    ingestion = None
                if isinstance(ingestion, dict):
                    imported_at = str(ingestion.get("imported_at") or "")
                    inputs = ingestion.get("inputs") or {}
                    if not isinstance(inputs, dict):
                        inputs = {}
                    if isinstance(inputs.get("pdf"), dict):
                        source_pdf_path = inputs["pdf"].get("original_path")
                    if isinstance(inputs.get("text"), dict):
                        source_text_path = inputs["text"].get("original_path")
                    # Use filename as a title when available.
                    orig = source_pdf_path or source_text_path
                    if orig:
                        try:
                            title = Path(str(orig)).name
                        except Exception:
                            title = str(orig)

            meeting_date: Optional[str] = None
            try:
                datetime.strptime(meeting_id, "%Y-%m-%d")
                meeting_date = meeting_id
            except Exception:
                meeting_date = _guess_meeting_date(meeting_id)

            meeting_location: Optional[str] = None
            try:
                meeting_json = json.loads((meeting_dir / "meeting.json").read_text(encoding="utf-8"))
            except Exception:
                meeting_json = None
            if isinstance(meeting_json, dict):
                d = meeting_json.get("meeting_date")
                loc = meeting_json.get("meeting_location")
                if d and meeting_date is None:
                    meeting_date = str(d)
                if loc:
                    meeting_location = str(loc)
            if meeting_location is None:
                try:
                    p = meeting_dir / "extracted_text.txt"
                    if not p.exists():
                        p = meeting_dir / "extracted_text_from_txt.txt"
                    if p.exists():
                        head = p.read_text(encoding="utf-8", errors="replace")
                        _d2, loc2 = extract_meeting_metadata(head)
                        if loc2:
                            meeting_location = loc2
                except Exception:
                    pass

            # Best-effort: populate the DB index so future requests succeed.
            try:
                upsert_meeting(
                    db_path=db_path,
                    meeting_id=meeting_id,
                    imported_at=imported_at or "",
                    meeting_dir=meeting_dir,
                    meeting_date=meeting_date,
                    meeting_location=meeting_location,
                    title=title,
                    source_pdf_path=(str(source_pdf_path) if source_pdf_path else None),
                    source_text_path=(str(source_text_path) if source_text_path else None),
                )
            except Exception:
                pass

            # Re-load via DB path so the response shape stays consistent.
            row = get_meeting(db_path=db_path, meeting_id=meeting_id)
            if row is None:
                # Last resort: synthesize the response directly.
                class _Row:
                    def __init__(self) -> None:
                        self.meeting_id = meeting_id
                        self.imported_at = imported_at
                        self.meeting_date = meeting_date
                        self.meeting_location = meeting_location
                        self.title = title
                        self.meeting_dir = str(meeting_dir)
                        self.source_pdf_path = str(source_pdf_path) if source_pdf_path else None
                        self.source_text_path = str(source_text_path) if source_text_path else None

                row = _Row()  # type: ignore[assignment]

        artifact_names: list[str] = []
        try:
            artifact_names = list_meeting_artifact_names(db_path=db_path, meeting_id=meeting_id)
        except Exception:
            artifact_names = []

        artifacts: dict[str, object] = {}
        for name in artifact_names:
            try:
                obj = get_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name=name)
            except Exception:
                obj = None
            if obj is not None:
                artifacts[name] = obj

        # If SQLite mirroring didn't happen (or older meeting folder), fall back to disk
        # for a small, stable set of standard artifacts and opportunistically mirror them.
        standard: list[tuple[str, str]] = [
            ("agenda_items", "agenda_items.json"),
            ("attachments", "attachments.json"),
            ("agenda_pass_a", "agenda_pass_a.json"),
            ("interest_pass_b", "interest_pass_b.json"),
            ("things_you_care_about", "things_you_care_about.json"),
            ("meeting_pass_c", "meeting_pass_c.json"),
        ]
        try:
            meeting_dir = Path(row.meeting_dir)
        except Exception:
            meeting_dir = None

        for name, filename in standard:
            if name in artifacts:
                continue
            if meeting_dir is None:
                continue
            try:
                p = meeting_dir / filename
                if not p.exists():
                    continue
                obj = json.loads(p.read_text(encoding="utf-8"))
                artifacts[name] = obj
                try:
                    upsert_meeting_artifact(db_path=db_path, meeting_id=meeting_id, name=name, obj=obj)
                    if name not in artifact_names:
                        artifact_names.append(name)
                except Exception:
                    pass
            except Exception:
                continue

        resp = {
            "meeting": {
                "meeting_id": row.meeting_id,
                "imported_at": row.imported_at,
                "meeting_date": row.meeting_date,
                "meeting_location": getattr(row, "meeting_location", None),
                "title": row.title,
                "meeting_dir": row.meeting_dir,
                "source_pdf_path": row.source_pdf_path,
                "source_text_path": row.source_text_path,
            },
            "artifact_names": artifact_names,
            "artifacts": artifacts,
            "raw": {
                "meeting_json": f"/raw/{meeting_id}/meeting.json",
                "ingestion_json": f"/raw/{meeting_id}/ingestion.json",
                "agenda_items_json": f"/raw/{meeting_id}/agenda_items.json",
                "attachments_json": f"/raw/{meeting_id}/attachments.json",
                "agenda_pass_a_json": f"/raw/{meeting_id}/agenda_pass_a.json",
                "things_you_care_about_json": f"/raw/{meeting_id}/things_you_care_about.json",
                "meeting_pass_c_json": f"/raw/{meeting_id}/meeting_pass_c.json",
            },
        }
        self._send_json(200, resp)

    def _handle_import_json(self, *, store_dir: Path) -> None:
        store_dir, err = validate_store_dir(store_dir=store_dir)
        if err:
            self._send_json_error(500, err)
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except Exception:
            length = 0

        max_bytes = 200 * 1024 * 1024  # 200 MiB
        if length and length > max_bytes:
            self._send_json_error(413, f"Upload exceeds limit ({max_bytes // (1024 * 1024)} MiB).")
            return

        ctype = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in ctype:
            self._send_json_error(400, "Expected multipart/form-data.")
            return

        try:
            body = self.rfile.read(length) if length > 0 else b""
        except Exception as e:
            self._send_json_error(400, f"Failed to read upload body: {type(e).__name__}: {e}")
            return

        try:
            form = self._parse_multipart_form_data(body=body, content_type=ctype)
        except Exception as e:
            self._send_json_error(400, f"Failed to parse upload: {type(e).__name__}: {e}")
            return

        def _write_upload(*, field: str, default_name: str, force_ext: Optional[str] = None) -> Optional[Path]:
            part = form.get(field)
            if not isinstance(part, dict):
                return None

            data = part.get("data")
            original_name = part.get("filename")
            if not isinstance(data, (bytes, bytearray)) or not data:
                return None

            if not isinstance(original_name, str) or not original_name:
                original_name = default_name

            original_name = str(original_name)
            safe_name = Path(original_name).name
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name).strip("_") or default_name
            if force_ext is not None and not safe_name.lower().endswith(force_ext.lower()):
                safe_name = safe_name + force_ext

            uploads_dir = (store_dir / "_uploads").resolve()
            uploads_dir.mkdir(parents=True, exist_ok=True)

            upload_path = uploads_dir / (f"upload_{time.time_ns()}_{os.getpid()}_{safe_name}")
            with upload_path.open("wb") as f:
                f.write(bytes(data))
            return upload_path

        try:
            pdf_upload_path = _write_upload(field="pdf", default_name="upload.pdf", force_ext=".pdf")
            text_upload_path = _write_upload(field="text", default_name="upload.txt", force_ext=".txt")
        except Exception as e:
            self._send_json_error(400, f"Failed to save upload: {type(e).__name__}: {e}")
            return

        if pdf_upload_path is None and text_upload_path is None:
            self._send_json_error(400, "No file selected.")
            return

        try:
            imported = import_meeting(store_dir=store_dir, pdf_path=pdf_upload_path, text_path=text_upload_path)
        except IngestionError as e:
            self._send_json_error(400, str(e))
            return
        except Exception as e:
            self._send_json_error(500, f"{type(e).__name__}: {e}")
            return

        try:
            sync_store_dir_to_db(store_dir=store_dir)
        except Exception:
            pass

        self._send_json(
            200,
            {
                "meeting_id": imported.meeting_id,
                "redirect": f"/meetings/{imported.meeting_id}",
            },
        )

    def _handle_import(self, *, store_dir: Path) -> None:
        store_dir, err = validate_store_dir(store_dir=store_dir)
        if err:
            self._render_error_page(title="Store directory error", message=err, status=500)
            return
        # Basic size guardrail: keep accidental huge uploads from wedging the server.
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except Exception:
            length = 0

        max_bytes = 200 * 1024 * 1024  # 200 MiB
        if length and length > max_bytes:
            self._render_error_page(
                title="Upload too large",
                message=f"PDF exceeds upload limit ({max_bytes // (1024 * 1024)} MiB).",
                status=413,
            )
            return

        ctype = self.headers.get("Content-Type") or ""
        if "multipart/form-data" not in ctype:
            self._render_error_page(title="Bad request", message="Expected multipart/form-data.")
            return

        # Read request body (bounded by max_bytes above).
        try:
            body = self.rfile.read(length) if length > 0 else b""
        except Exception as e:
            self._render_error_page(title="Bad request", message=f"Failed to read upload body: {type(e).__name__}: {e}")
            return

        # Parse multipart form.
        try:
            form = self._parse_multipart_form_data(body=body, content_type=ctype)
        except Exception as e:
            self._render_error_page(title="Bad request", message=f"Failed to parse upload: {type(e).__name__}: {e}")
            return

        def _write_upload(*, field: str, default_name: str, force_ext: Optional[str] = None) -> Optional[Path]:
            part = form.get(field)
            if not isinstance(part, dict):
                return None

            data = part.get("data")
            original_name = part.get("filename")
            if not isinstance(data, (bytes, bytearray)) or not data:
                return None

            if not isinstance(original_name, str) or not original_name:
                original_name = default_name

            original_name = str(original_name)
            safe_name = Path(original_name).name
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name).strip("_") or default_name
            if force_ext is not None and not safe_name.lower().endswith(force_ext.lower()):
                safe_name = safe_name + force_ext

            uploads_dir = (store_dir / "_uploads").resolve()
            uploads_dir.mkdir(parents=True, exist_ok=True)

            # Collision-resistant temporary filename; stable meeting_id is derived from file hash.
            upload_path = uploads_dir / (f"upload_{time.time_ns()}_{os.getpid()}_{safe_name}")

            with upload_path.open("wb") as f:
                f.write(bytes(data))
            return upload_path

        try:
            pdf_upload_path = _write_upload(field="pdf", default_name="upload.pdf", force_ext=".pdf")
        except Exception as e:
            self._render_error_page(title="Upload failed", message=f"Failed to save uploaded PDF: {type(e).__name__}: {e}")
            return

        try:
            text_upload_path = _write_upload(field="text", default_name="upload.txt", force_ext=".txt")
        except Exception as e:
            self._render_error_page(title="Upload failed", message=f"Failed to save uploaded text file: {type(e).__name__}: {e}")
            return

        if pdf_upload_path is None and text_upload_path is None:
            self._render_error_page(title="Bad request", message="No file selected.")
            return

        # Import into canonical meeting folder structure.
        try:
            imported = import_meeting(store_dir=store_dir, pdf_path=pdf_upload_path, text_path=text_upload_path)
        except IngestionError as e:
            # Keep this user-friendly (A1 DoD).
            self._render_error_page(title="Import failed", message=str(e), status=400)
            return
        except Exception as e:
            self._render_error_page(title="Import failed", message=f"{type(e).__name__}: {e}", status=500)
            return

        # Ensure the meetings list DB reflects the new folder.
        sync_store_dir_to_db(store_dir=store_dir)

        # Redirect to the new meeting page.
        self.send_response(303)
        self.send_header("Location", f"/meetings/{imported.meeting_id}")
        self.end_headers()
        return

    def do_GET(self) -> None:  # noqa: N802
        store_dir: Path = self.server.store_dir  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/meetings":
            sd = self._store_dir_or_json_error()
            if sd is None:
                return
            self._api_meeting_list(store_dir=sd)
            return

        if path.startswith("/api/meetings/"):
            sd = self._store_dir_or_json_error()
            if sd is None:
                return
            meeting_id = path.removeprefix("/api/meetings/").strip("/")
            if not meeting_id:
                self._send_json_error(400, "Missing meeting_id")
                return
            self._api_meeting_detail(store_dir=sd, meeting_id=meeting_id)
            return

        if path == "/":
            sd = self._store_dir_or_error()
            if sd is None:
                return
            html = render_meeting_list_html(store_dir=store_dir)
            self._send(200, html.encode("utf-8"), content_type="text/html; charset=utf-8")
            return

        if path.startswith("/meetings/"):
            sd = self._store_dir_or_error()
            if sd is None:
                return
            meeting_id = path.removeprefix("/meetings/")
            html = render_meeting_detail_html(store_dir=store_dir, meeting_id=meeting_id)
            self._send(200, html.encode("utf-8"), content_type="text/html; charset=utf-8")
            return

        if path.startswith("/raw/"):
            sd = self._store_dir_or_error()
            if sd is None:
                return
            # /raw/<meeting_id>/meeting.json or /raw/<meeting_id>/ingestion.json
            rest = path.removeprefix("/raw/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) == 2:
                meeting_id, filename = parts
                if filename in {
                    "meeting.json",
                    "ingestion.json",
                    "agenda_items.json",
                    "attachments.json",
                    "agenda_pass_a.json",
                    "interest_pass_b.json",
                    "things_you_care_about.json",
                    "meeting_pass_c.json",
                    "extracted_text.txt",
                    "extracted_text_from_txt.txt",
                }:
                    db_path = sync_store_dir_to_db(store_dir=store_dir)
                    row = get_meeting(db_path=db_path, meeting_id=meeting_id)
                    if row is None:
                        self._send(404, b"Not found", content_type="text/plain; charset=utf-8")
                        return
                    fpath = Path(row.meeting_dir) / filename
                    if fpath.exists():
                        if filename.endswith(".json"):
                            ct = "application/json; charset=utf-8"
                        else:
                            ct = "text/plain; charset=utf-8"
                        self._send(200, fpath.read_bytes(), content_type=ct)
                        return
            self._send(404, b"Not found", content_type="text/plain; charset=utf-8")
            return

        self._send(404, b"Not found", content_type="text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        store_dir: Path = self.server.store_dir  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/import":
            sd = self._store_dir_or_json_error()
            if sd is None:
                return
            self._handle_import_json(store_dir=sd)
            return

        if path == "/import":
            self._handle_import(store_dir=store_dir)
            return

        if path.startswith("/api/meetings/") and path.endswith("/chat"):
            sd = self._store_dir_or_json_error()
            if sd is None:
                return
            meeting_id = path.removeprefix("/api/meetings/").removesuffix("/chat")
            meeting_id = meeting_id.strip("/")
            try:
                payload = self._read_json_body()
            except Exception:
                self._send_json_error(400, "Invalid JSON")
                return

            question = ""
            if isinstance(payload, dict) and isinstance(payload.get("question"), str):
                question = payload.get("question") or ""
            question = question.strip()
            if not question:
                self._send_json_error(400, "Missing 'question'")
                return

            try:
                resp = answer_question(store_dir=sd, meeting_id=meeting_id, question=question)
            except FileNotFoundError:
                self._send_json_error(404, "Not found")
                return
            except Exception as e:
                self._send_json_error(500, f"{type(e).__name__}: {e}")
                return

            self._send_json(200, resp)
            return

        if path.startswith("/api/meetings/") and path.endswith("/rerun"):
            sd = self._store_dir_or_json_error()
            if sd is None:
                return
            meeting_id = path.removeprefix("/api/meetings/").removesuffix("/rerun").strip("/")
            if not meeting_id:
                self._send_json_error(400, "Missing meeting_id")
                return

            try:
                payload = self._read_json_body()
            except Exception:
                self._send_json_error(400, "Invalid JSON")
                return
            if not isinstance(payload, dict):
                payload = {}

            def _bool(name: str, default: bool = False) -> bool:
                v = payload.get(name, default)
                return bool(v)

            profile = payload.get("profile")
            profile_path = str(profile).strip() if isinstance(profile, str) and profile.strip() else None

            try:
                res = rerun_meeting(
                    store_dir=sd,
                    meeting_id=meeting_id,
                    profile_path=profile_path,
                    summarize_all_items=_bool("summarize_all_items", False),
                    classify_relevance=_bool("classify_relevance", True),
                    summarize_meeting=_bool("summarize_meeting", True),
                )
            except FileNotFoundError as e:
                msg = str(e)
                if "Meeting folder not found" in msg or "meeting.json not found" in msg:
                    self._send_json_error(404, "Not found")
                else:
                    self._send_json_error(409, msg)
                return
            except Exception as e:
                self._send_json_error(400, f"Re-run failed: {type(e).__name__}: {e}")
                return

            try:
                sync_store_dir_to_db(store_dir=sd)
            except Exception:
                pass

            self._send_json(
                200,
                {
                    "meeting_id": meeting_id,
                    "generated_at": getattr(res, "generated_at", None),
                    "ran_pass_a": bool(getattr(res, "ran_pass_a", False)),
                    "ran_pass_b": bool(getattr(res, "ran_pass_b", False)),
                    "ran_pass_c": bool(getattr(res, "ran_pass_c", False)),
                },
            )
            return

        if path.startswith("/meetings/") and path.endswith("/rerun"):
            meeting_id = path.removeprefix("/meetings/").removesuffix("/rerun")
            meeting_id = meeting_id.strip("/")
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except Exception:
                length = 0
            body = self.rfile.read(length) if length > 0 else b""
            form = parse_qs(body.decode("utf-8", errors="replace"))

            def has_flag(name: str) -> bool:
                return name in form and any(v for v in form.get(name, []) if str(v).strip())

            profile = None
            if "profile" in form and form["profile"]:
                profile = str(form["profile"][0]).strip() or None

            try:
                rerun_meeting(
                    store_dir=store_dir,
                    meeting_id=meeting_id,
                    profile_path=profile,
                    summarize_all_items=has_flag("summarize_all_items"),
                    classify_relevance=has_flag("classify_relevance"),
                    summarize_meeting=has_flag("summarize_meeting"),
                )
            except Exception as e:
                msg = f"Re-run failed: {type(e).__name__}: {e}".encode("utf-8")
                self._send(400, msg, content_type="text/plain; charset=utf-8")
                return

            # Redirect back to the meeting page.
            self.send_response(303)
            self.send_header("Location", f"/meetings/{meeting_id}")
            self.end_headers()
            return

        self._send(404, b"Not found", content_type="text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        # Keep test output and CLI usage quiet suggests minimal logging.
        return

    def _send(self, status: int, data: bytes, *, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(*, store_dir: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    # Validate but do not crash: if invalid, keep the server running and show a clear UI error.
    store_dir = store_dir.expanduser()
    try:
        store_dir = store_dir.resolve()
    except Exception:
        pass

    httpd = ThreadingHTTPServer((host, int(port)), _Handler)
    httpd.store_dir = store_dir  # type: ignore[attr-defined]

    # Ensure DB is ready and indexed at startup when possible.
    try:
        sync_store_dir_to_db(store_dir=store_dir)
    except Exception:
        # Validation and request handlers will render a clear error.
        pass

    try:
        httpd.serve_forever(poll_interval=0.25)
    finally:
        httpd.server_close()
