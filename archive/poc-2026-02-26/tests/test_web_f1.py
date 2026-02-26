from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike.db import DB_FILENAME, list_meetings
from minutes_spike.store import import_meeting
from minutes_spike.web import render_meeting_list_html


def test_f1_meeting_list_uses_sqlite_and_renders_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "My Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    # Avoid depending on real PDF parsing libs/content.
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_dir = tmp_path / "store"
    imported = import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    db_path = store_dir / DB_FILENAME
    assert db_path.exists()

    meetings = list_meetings(db_path=db_path)
    assert [m.meeting_id for m in meetings] == ["2026-01-09"]
    assert meetings[0].title == "My Agenda Packet.pdf"

    html = render_meeting_list_html(store_dir=store_dir)
    assert "/meetings/2026-01-09" in html
    assert "My Agenda Packet.pdf" in html
    assert "2026-01-09" in html


def test_f1_meeting_list_shows_analysis_badges_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_dir = tmp_path / "store"
    imported = import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    # Simulate that Pass C was generated and stored.
    (imported.meeting_dir / "meeting_pass_c.json").write_text(
        json.dumps({"meeting_id": "2026-01-09", "highlights": [], "ordinances_resolutions": [], "watchlist_hits": []})
        + "\n",
        encoding="utf-8",
    )
    meeting_obj = json.loads((imported.meeting_dir / "meeting.json").read_text(encoding="utf-8"))
    meeting_obj["meeting_pass_c"] = {"stored_path": str(imported.meeting_dir / "meeting_pass_c.json")}
    (imported.meeting_dir / "meeting.json").write_text(json.dumps(meeting_obj, indent=2) + "\n", encoding="utf-8")

    html = render_meeting_list_html(store_dir=store_dir)
    assert "Pass C" in html
