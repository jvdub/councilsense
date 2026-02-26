from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike import cli


def test_profile_edits_change_highlights_for_same_meeting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fixed input meeting text.
    minutes_text = "1. CALL TO ORDER\nSunset Flats was discussed.\n2. ADJOURNMENT\n"
    text_path = tmp_path / "minutes.txt"
    text_path.write_text(minutes_text, encoding="utf-8")

    # Profile A: should alert on Sunset Flats.
    profile_a = tmp_path / "profile_a.yaml"
    profile_a.write_text(
        """rules:
  - id: neighborhood
    description: Neighborhood
    type: keyword_any
    enabled: true
    keywords: ["sunset flats"]
    min_hits: 1
output: {evidence: {snippet_chars: 50, max_snippets_per_rule: 3}}
""",
        encoding="utf-8",
    )

    # Profile B: no relevant keywords => no alert.
    profile_b = tmp_path / "profile_b.yaml"
    profile_b.write_text(
        """rules:
  - id: neighborhood
    description: Neighborhood
    type: keyword_any
    enabled: true
    keywords: ["not present"]
    min_hits: 1
output: {evidence: {snippet_chars: 50, max_snippets_per_rule: 3}}
""",
        encoding="utf-8",
    )

    out_a = tmp_path / "out_a.json"
    out_b = tmp_path / "out_b.json"

    rc_a = cli.main(["--text", str(text_path), "--profile", str(profile_a), "--out", str(out_a)])
    rc_b = cli.main(["--text", str(text_path), "--profile", str(profile_b), "--out", str(out_b)])
    assert rc_a == 0
    assert rc_b == 0

    payload_a = json.loads(out_a.read_text(encoding="utf-8"))
    payload_b = json.loads(out_b.read_text(encoding="utf-8"))

    assert payload_a["alert"] is True
    assert payload_b["alert"] is False


def test_init_profile_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point XDG_CONFIG_HOME at tmp to avoid touching real user config.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    rc = cli.main(["--init-profile"])
    assert rc == 0

    created = tmp_path / "xdg" / "councilsense" / "interest_profile.yaml"
    assert created.exists()
    text = created.read_text(encoding="utf-8")

    # Basic smoke: ensure the three initial interest areas exist.
    assert "neighborhood_sunset_flats" in text
    assert "city_code_changes_residential" in text
    assert "laundromat_new_or_approved" in text
