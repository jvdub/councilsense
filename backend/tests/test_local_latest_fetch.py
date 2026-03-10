from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from councilsense.app.local_latest_fetch import LatestFetchError, extract_latest_candidate, fetch_latest_meeting
from councilsense.app.multi_document_compose import assemble_summarize_compose_input
from councilsense.db import CanonicalDocumentRepository
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


def test_extract_latest_candidate_supports_latest_offset() -> None:
    candidate = extract_latest_candidate(
        html=_fixture_html(),
        source_url="https://www.eaglemountain.gov/agenda-center",
        latest_offset=1,
    )

    assert candidate.meeting_date_iso == "2025-12-10"
    assert candidate.candidate_url.endswith("/agenda/2025-12-10-minutes.pdf")


def test_extract_latest_candidate_raises_when_offset_exceeds_candidate_count() -> None:
    with pytest.raises(LatestFetchError, match="latest_offset=2"):
        extract_latest_candidate(
            html=_fixture_html(),
            source_url="https://www.eaglemountain.gov/agenda-center",
            latest_offset=2,
        )


def test_fetch_latest_meeting_is_idempotent_for_unchanged_source(tmp_path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)

    def _stub_fetch(url: str, __: float) -> bytes:
        if "/events?" in url or url.endswith("/events"):
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


def test_fetch_latest_meeting_persists_supported_civicclerk_bundle_documents(tmp_path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)

    def _stub_fetch(url: str, __: float) -> bytes:
        if "/events?" in url or url.endswith("/events"):
            return (
                '{"value":[{"id":735,"eventName":"City Council Meeting","eventDate":"2026-02-03T00:00:00Z",'
                '"publishedFiles":['
                '{"type":"Minutes","name":"Approved Minutes","fileId":1638,"url":"stream/approved-minutes.pdf"},'
                '{"type":"Agenda","name":"Agenda","fileId":1639,"url":"stream/agenda.pdf"},'
                '{"type":"Agenda Packet","name":"Agenda Packet","fileId":1640,"url":"stream/agenda-packet.pdf"}'
                ']}]}'
            ).encode("utf-8")
        if "GetMeetingFile(" in url and "fileId=1638" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/minutes-1638.txt"}'
        if "GetMeetingFile(" in url and "fileId=1638" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/minutes-1638.pdf"}'
        if "GetMeetingFile(" in url and "fileId=1639" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/agenda-1639.txt"}'
        if "GetMeetingFile(" in url and "fileId=1639" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/agenda-1639.pdf"}'
        if "GetMeetingFile(" in url and "fileId=1640" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/packet-1640.txt"}'
        if "GetMeetingFile(" in url and "fileId=1640" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/packet-1640.pdf"}'
        if url.endswith("minutes-1638.txt"):
            return b"Council approved the February 3, 2026 minutes and adopted the Youth Council ordinance."
        if url.endswith("agenda-1639.txt"):
            return b"Agenda includes future land use map discussion, quarterly financial report, and legislative update."
        if url.endswith("packet-1640.txt"):
            return b"Packet contains the staff report, map, presentation, ordinance text, and Hidden Hollow amenity packet."
        return b"%PDF-1.7\nmock pdf bytes"

    result = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=2.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
    )

    documents = CanonicalDocumentRepository(connection).list_documents_for_meeting(meeting_id=result.meeting_id)
    assert {document.document_kind for document in documents} == {"minutes", "agenda", "packet"}

    compose_input = assemble_summarize_compose_input(
        connection=connection,
        meeting_id=result.meeting_id,
        fallback_source_type=None,
        fallback_text="",
    )
    assert compose_input.source_coverage.statuses == {
        "minutes": "present",
        "agenda": "present",
        "packet": "present",
    }
    assert "future land use map discussion" in compose_input.composed_text.lower()
    assert "hidden hollow amenity packet" in compose_input.composed_text.lower()
    stage_metadata = result.stage_outcomes[0]["metadata"]
    assert isinstance(stage_metadata, dict)
    assert stage_metadata["published_document_kinds"] == ["minutes", "agenda", "packet"]
