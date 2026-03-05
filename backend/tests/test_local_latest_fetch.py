from __future__ import annotations

import sqlite3
from pathlib import Path

from councilsense.app.local_latest_fetch import extract_latest_candidate, fetch_latest_meeting
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


def _fixture_html() -> str:
    return """
    <html>
      <head><title>Agenda Center</title></head>
      <body>
        <a href="/agenda/2025-12-10-minutes.pdf">City Council Minutes - 12/10/2025</a>
        <a href="/agenda/2026-01-14-minutes.pdf">City Council Minutes - 01/14/2026</a>
      </body>
    </html>
    """


def test_extract_latest_candidate_prefers_most_recent_meeting_date() -> None:
    candidate = extract_latest_candidate(
        html=_fixture_html(),
        source_url="https://www.eaglemountain.gov/agenda-center",
    )

    assert candidate.meeting_date_iso == "2026-01-14"
    assert candidate.candidate_url.endswith("/agenda/2026-01-14-minutes.pdf")
    assert "City Council Minutes" in candidate.title


def test_fetch_latest_meeting_is_idempotent_for_unchanged_source(tmp_path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)

    def _stub_fetch(url: str, __: float) -> bytes:
        if url.endswith("/events"):
            return (
                '{"value":[{"id":10,"eventName":"City Council Meeting","eventDate":"2026-01-14T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","url":"stream/2026-01-14-minutes.pdf"}]}]}'
            ).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/minutes.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/minutes.pdf"}'
        if url.endswith("minutes.txt"):
            return b"City Council approved minutes for January 14, 2026."
        return b"%PDF-1.7\nmock pdf bytes"

    first = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=2.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
    )
    second = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=2.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
    )

    assert first.meeting_id == second.meeting_id
    assert first.fingerprint == second.fingerprint

    meetings_count = connection.execute("SELECT COUNT(*) FROM meetings WHERE city_id = ?", (PILOT_CITY_ID,)).fetchone()
    assert meetings_count is not None
    assert int(meetings_count[0]) == 1
