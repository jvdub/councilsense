from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from minutes_spike import cli


def test_classify_relevance_includes_attachment_backed_highlight(tmp_path: Path) -> None:
    # Agenda items contain no watchlist terms; the mention exists only in an exhibit/attachment.
    text = (
        "1. CALL TO ORDER\n"
        "Nothing relevant here.\n\n"
        "2. ADJOURNMENT\n"
        "Meeting ended.\n\n"
        "EXHIBIT A: PLAT - SUNSET FLATS PHASE 'A'\n"
        "Township 1 South Range 1 East Salt Lake Base and Meridian\n"
    )

    minutes_path = tmp_path / "minutes.txt"
    minutes_path.write_text(text, encoding="utf-8")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: neighborhood
                description: Neighborhood mention
                type: keyword_any
                enabled: true
                keywords: ["sunset flats"]
                min_hits: 1

            output:
              evidence:
                snippet_chars: 80
                max_snippets_per_rule: 5
            """
        ),
        encoding="utf-8",
    )

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--text",
            str(minutes_path),
            "--profile",
            str(profile_path),
            "--classify-relevance",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    highlights = payload.get("things_you_care_about")
    assert isinstance(highlights, list)

    # Find an attachment-backed highlight.
    att_highlights = [
        h
        for h in highlights
        if isinstance(h, dict)
        and isinstance(h.get("links"), dict)
        and isinstance(h["links"].get("attachment"), dict)
    ]
    assert att_highlights, "Expected at least one attachment-backed highlight"

    h0 = att_highlights[0]
    assert h0.get("category") == "neighborhood"

    ev = h0.get("evidence")
    assert isinstance(ev, list) and 1 <= len(ev) <= 3
    assert ev[0].get("bucket") == "attachment"

    att = ev[0].get("attachment")
    assert isinstance(att, dict)
    assert isinstance(att.get("attachment_id"), str) and att.get("attachment_id")

    snippet = str(ev[0].get("snippet") or "").lower()
    assert "sunset" in snippet

