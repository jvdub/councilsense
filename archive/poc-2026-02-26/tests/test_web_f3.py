from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike import llm
from minutes_spike.rerun import rerun_meeting
from minutes_spike.store import import_meeting
from minutes_spike.web import render_meeting_detail_html


def test_f3_meeting_detail_includes_rerun_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    html = render_meeting_detail_html(store_dir=store_dir, meeting_id="2026-01-09")
    assert "/meetings/2026-01-09/rerun" in html
    assert "Re-run analysis" in html


def test_f3_rerun_overwrites_pass_b_and_pass_c(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    # Keep extraction deterministic and include a keyword that will hit the default profile rules (ordinance).
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "1. CALL TO ORDER\nHello\n\n2.A. ORDINANCE / PUBLIC HEARING - CODE UPDATE\nAn Ordinance to amend the City Code.\n",
        ),
    )

    # Create a minimal profile with a single rule.
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules:\n"
        "  - id: code\n"
        "    description: Code changes\n"
        "    type: keyword_any\n"
        "    enabled: true\n"
        "    keywords: [\"ordinance\"]\n"
        "    min_hits: 1\n"
        "output: {evidence: {snippet_chars: 120, max_snippets_per_rule: 3}}\n",
        encoding="utf-8",
    )

    store_dir = tmp_path / "store"
    imported = import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    # Run rerun (Pass B + Pass C only).
    res = rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=False,
        classify_relevance=True,
        summarize_meeting=True,
    )

    assert res.ran_pass_b is True
    assert res.ran_pass_c is True

    meeting_obj = json.loads((imported.meeting_dir / "meeting.json").read_text(encoding="utf-8"))
    assert "things_you_care_about" in meeting_obj
    assert Path(meeting_obj["things_you_care_about"]["stored_path"]).exists()
    assert "meeting_pass_c" in meeting_obj
    assert Path(meeting_obj["meeting_pass_c"]["stored_path"]).exists()

    things = json.loads(Path(meeting_obj["things_you_care_about"]["stored_path"]).read_text(encoding="utf-8"))
    assert isinstance(things, list)
    assert len(things) >= 1

    summary = json.loads(Path(meeting_obj["meeting_pass_c"]["stored_path"]).read_text(encoding="utf-8"))
    assert "highlights" in summary
