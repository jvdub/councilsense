from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike.chat import answer_question
from minutes_spike.store import import_meeting
from minutes_spike.web import render_meeting_detail_html


def test_g1_meeting_detail_includes_chat_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    html = render_meeting_detail_html(store_dir=store_dir, meeting_id="2026-01-09")
    assert "/api/meetings/2026-01-09/chat" in html


def test_g1_why_was_sunset_flats_mentioned_cites_attachment_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    # Construct a minimal packet that yields at least one attachment containing Sunset Flats.
    # We include an agenda section first, then an attachment heading.
    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.A. DISCUSSION - HOUSING\nGeneral discussion.\n\n"
        "ATTACHMENT 1: Staff Report\n"
        "Project: Sunset Flats\n"
        "This staff report mentions Sunset Flats as part of the proposal.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    resp = answer_question(store_dir=store_dir, meeting_id="2026-01-09", question="Why was Sunset Flats mentioned?")

    assert resp["found"] is True
    assert isinstance(resp.get("evidence"), list)
    assert resp["evidence"], "Expected evidence snippets"

    first = resp["evidence"][0]
    assert first.get("bucket") == "attachment"
    assert "Sunset Flats" in (first.get("snippet") or "")
    assert isinstance(first.get("attachment"), dict)

    # Stronger sanity: attachment artifacts exist on disk.
    attachments_path = store_dir / "2026-01-09" / "attachments.json"
    assert attachments_path.exists()
    attachments = json.loads(attachments_path.read_text(encoding="utf-8"))
    assert isinstance(attachments, list)
    assert any("Sunset Flats" in (str(a.get("body_text") or "") + str(a.get("title") or "")) for a in attachments if isinstance(a, dict))
