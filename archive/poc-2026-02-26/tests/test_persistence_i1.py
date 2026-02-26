from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from minutes_spike.db import DB_FILENAME, get_meeting_artifact
from minutes_spike.rerun import rerun_meeting
from minutes_spike.store import import_meeting
from minutes_spike.web import render_meeting_detail_html, render_meeting_list_html


def test_i1_import_mirrors_agenda_items_and_attachments_into_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.A. DISCUSSION - HOUSING\nGeneral discussion.\n\n"
        "ATTACHMENT 1: Staff Report\nProject: Sunset Flats\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    db_path = store_dir / DB_FILENAME

    agenda = get_meeting_artifact(db_path=db_path, meeting_id="2026-01-09", name="agenda_items")
    assert isinstance(agenda, list) and agenda

    atts = get_meeting_artifact(db_path=db_path, meeting_id="2026-01-09", name="attachments")
    assert isinstance(atts, list)


def test_i1_rerun_mirrors_pass_b_and_pass_c_into_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.C. CONDITIONAL USE PERMIT - NEW LAUNDROMAT\n"
        "Staff recommended approval. Motion to approve carried unanimously.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: laundromat
                description: New laundromats
                type: keyword_any
                enabled: true
                keywords: ["laundromat", "laundromats"]
                min_hits: 1

            output:
              evidence:
                snippet_chars: 120
                max_snippets_per_rule: 3
            """
        ),
        encoding="utf-8",
    )

    rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=False,
        classify_relevance=True,
        summarize_meeting=True,
    )

    db_path = store_dir / DB_FILENAME

    pb = get_meeting_artifact(db_path=db_path, meeting_id="2026-01-09", name="interest_pass_b")
    assert isinstance(pb, list)

    things = get_meeting_artifact(db_path=db_path, meeting_id="2026-01-09", name="things_you_care_about")
    assert isinstance(things, list)

    pc = get_meeting_artifact(db_path=db_path, meeting_id="2026-01-09", name="meeting_pass_c")
    assert isinstance(pc, dict)


def test_i1_web_pages_render_without_reading_analysis_json_files_when_db_has_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.C. CONDITIONAL USE PERMIT - NEW LAUNDROMAT\n"
        "Staff recommended approval. Motion to approve carried unanimously.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: laundromat
                description: New laundromats
                type: keyword_any
                enabled: true
                keywords: ["laundromat"]
                min_hits: 1

            output:
              evidence:
                snippet_chars: 120
                max_snippets_per_rule: 3
            """
        ),
        encoding="utf-8",
    )

    rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=False,
        classify_relevance=True,
        summarize_meeting=True,
    )

    # Guard: if the UI tries to read analysis JSON files from disk, fail.
    forbidden = {
        "meeting.json",
        "agenda_items.json",
        "attachments.json",
        "agenda_pass_a.json",
        "interest_pass_b.json",
        "things_you_care_about.json",
        "meeting_pass_c.json",
    }

    orig_read_text = Path.read_text

    def guarded_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.name in forbidden:
            raise RuntimeError(f"Unexpected read_text for {self.name}")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    html_list = render_meeting_list_html(store_dir=store_dir)
    assert "/meetings/2026-01-09" in html_list

    html_detail = render_meeting_detail_html(store_dir=store_dir, meeting_id="2026-01-09")
    assert "Things you care about" in html_detail
    assert "laundromat" in html_detail.lower()
