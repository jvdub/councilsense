from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike.db import DB_FILENAME, list_meetings
from minutes_spike.store import import_meeting
from minutes_spike.web import render_meeting_detail_html


def test_f2_meeting_detail_shows_summary_highlights_and_agenda_summaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "1. CALL TO ORDER\nHello\n\n2.A. DISCUSSION - PARKING\nStaff presented changes.\n",
        ),
    )

    store_dir = tmp_path / "store"
    imported = import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    meeting_dir = imported.meeting_dir

    # Fake Pass A, Pass B highlights, and Pass C summary artifacts as if CLI had run.
    (meeting_dir / "agenda_pass_a.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "1",
                    "title": "CALL TO ORDER",
                    "pass_a": {
                        "summary": ["Meeting opened."],
                        "citations": ["Mayor opened the meeting."],
                    },
                },
                {
                    "item_id": "2.A",
                    "title": "DISCUSSION - PARKING",
                    "pass_a": {
                        "summary": ["Staff presented parking updates."],
                        "citations": ["Staff presented changes."],
                    },
                },
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (meeting_dir / "things_you_care_about.json").write_text(
        json.dumps(
            [
                {
                    "title": "2.A: DISCUSSION - PARKING",
                    "category": "code_change",
                    "why": "Matched interest rule: Parking-related changes",
                    "confidence": 0.6,
                    "evidence": [
                        {
                            "bucket": "agenda_item",
                            "agenda_item": {"item_id": "2.A", "title": "DISCUSSION - PARKING"},
                            "snippet": "Staff presented changes.",
                        }
                    ],
                    "links": {"agenda_item": {"item_id": "2.A", "title": "DISCUSSION - PARKING"}},
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (meeting_dir / "meeting_pass_c.json").write_text(
        json.dumps(
            {
                "meeting_id": "2026-01-09",
                "highlights": [
                    {
                        "title": "2.A: DISCUSSION - PARKING",
                        "category": "meeting_highlight",
                        "why": "Staff presented parking updates.",
                        "confidence": 0.5,
                        "evidence": [
                            {
                                "bucket": "agenda_item",
                                "agenda_item": {"item_id": "2.A", "title": "DISCUSSION - PARKING"},
                                "snippet": "Staff presented changes.",
                            }
                        ],
                        "links": {"agenda_item": {"item_id": "2.A", "title": "DISCUSSION - PARKING"}},
                    }
                ],
                "ordinances_resolutions": [],
                "watchlist_hits": [{"category": "code_change", "count": 1}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Update meeting.json to point at the artifacts.
    meeting_json = json.loads((meeting_dir / "meeting.json").read_text(encoding="utf-8"))
    meeting_json["agenda_pass_a"] = {"stored_path": str(meeting_dir / "agenda_pass_a.json")}
    meeting_json["things_you_care_about"] = {"stored_path": str(meeting_dir / "things_you_care_about.json")}
    meeting_json["meeting_pass_c"] = {"stored_path": str(meeting_dir / "meeting_pass_c.json")}
    (meeting_dir / "meeting.json").write_text(json.dumps(meeting_json, indent=2) + "\n", encoding="utf-8")

    # Sanity: meeting exists in DB.
    db_path = store_dir / DB_FILENAME
    assert [m.meeting_id for m in list_meetings(db_path=db_path)] == ["2026-01-09"]

    html = render_meeting_detail_html(store_dir=store_dir, meeting_id="2026-01-09")
    assert "Meeting summary" in html
    assert "Things you care about" in html
    assert "Agenda items" in html
    assert "Staff presented parking updates." in html
    assert "Mayor opened the meeting." in html
    assert "Staff presented changes." in html
