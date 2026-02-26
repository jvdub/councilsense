from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from minutes_spike import cli


def test_prefilter_flags_agenda_items_and_attachments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Construct a minimal meeting-like text with an agenda section and an exhibit.
    text = (
        "1. CALL TO ORDER\n"
        "Nothing here.\n\n"
        "2.A. ORDINANCE / PUBLIC HEARING - ZONING UPDATE\n"
        "Consideration of an ordinance to amend residential setback rules.\n\n"
        "3. ADJOURNMENT\n"
        "Meeting ended.\n\n"
        "EXHIBIT A: PLAT - SUNSET FLATS PHASE 'A'\n"
        "Township 1 South Range 1 East Salt Lake Base and Meridian\n"
    )

    minutes_path = tmp_path / "minutes.txt"
    minutes_path.write_text(text, encoding="utf-8")

    profile_path = tmp_path / "profile.yaml"
    # Two rules: one should hit the ordinance agenda item; one should hit the exhibit.
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: code_change
                description: Code change
                type: keyword_with_context
                enabled: true
                keywords: ["ordinance"]
                context_keywords: ["amend", "residential"]
                window_chars: 200
                min_hits: 1

              - id: neighborhood
                description: Neighborhood
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
    rc = cli.main(["--text", str(minutes_path), "--profile", str(profile_path), "--out", str(out_path)])
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "prefilter" in payload

    rules = payload["prefilter"]["rules"]
    by_id = {r["rule_id"]: r for r in rules}

    code_rule = by_id["code_change"]
    assert any(c["item_id"] == "2.A" for c in code_rule["agenda_item_candidates"])

    neighborhood_rule = by_id["neighborhood"]
    assert len(neighborhood_rule["attachment_candidates"]) >= 1
    # Evidence snippets should be present.
    first_att = neighborhood_rule["attachment_candidates"][0]
    assert first_att["evidence"]
    assert "sunset" in (first_att["evidence"][0]["snippet"] or "").lower()
