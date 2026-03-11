from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pytest

from councilsense.app.discovery_sync import reconcile_discovered_meetings, sync_enumerated_meetings
from councilsense.app.provider_enumeration import CivicClerkSourceMeetingEnumerationProvider
from councilsense.db import (
    DiscoveredMeetingRepository,
    PILOT_CITY_ID,
    PILOT_CITY_SOURCE_ID,
    apply_migrations,
    seed_city_registry,
)
from councilsense.db.city_registry import CitySourceConfig


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    seed_city_registry(conn)
    try:
        yield conn
    finally:
        conn.close()


def _build_source() -> CitySourceConfig:
    return CitySourceConfig(
        id=PILOT_CITY_SOURCE_ID,
        city_id=PILOT_CITY_ID,
        source_type="minutes",
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        parser_name="civicclerk-events-api",
        parser_version="v1",
        health_status="unknown",
        last_success_at=None,
        last_attempt_at=None,
        failure_streak=0,
        last_failure_at=None,
        last_failure_reason=None,
    )


def _stub_fetch_with_payload(payload: dict[str, object]):
    def _stub_fetch(url: str, _: float) -> bytes:
        if "/Events?" in url or "/events?" in url:
            return json.dumps(payload).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b"<html></html>"
        raise AssertionError(f"Unexpected URL fetched: {url}")

    return _stub_fetch


def _insert_meeting_with_ingest_metadata(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    meeting_uid: str,
    metadata: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, meeting_uid, f"Meeting {meeting_id}"),
    )
    connection.execute(
        """
        INSERT INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            parser_version,
            source_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (f"run-{meeting_id}", PILOT_CITY_ID, f"cycle-{meeting_id}", "processed", "v1", "test-source"),
    )
    connection.execute(
        """
        INSERT INTO processing_stage_outcomes (
            id,
            run_id,
            city_id,
            meeting_id,
            stage_name,
            status,
            metadata_json,
            finished_at
        )
        VALUES (?, ?, ?, ?, 'ingest', 'processed', ?, ?)
        """,
        (
            f"outcome-{meeting_id}",
            f"run-{meeting_id}",
            PILOT_CITY_ID,
            meeting_id,
            json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            "2026-03-10T20:00:00Z",
        ),
    )


def test_provider_enumeration_sync_rerun_and_refresh_lifecycle(
    connection: sqlite3.Connection,
) -> None:
    provider = CivicClerkSourceMeetingEnumerationProvider()
    source = _build_source()

    first_payload = {
        "value": [
            {
                "id": 71,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-10T00:00:00Z",
                "publishedFiles": [
                    {"type": "Minutes", "name": "Minutes", "url": "stream/71-minutes.pdf"},
                ],
            }
        ]
    }
    second_payload = {
        "value": [
            {
                "id": 71,
                "eventName": "City Council Regular Session",
                "eventDate": "2026-03-11T00:00:00Z",
                "publishedFiles": [
                    {"type": "Minutes", "name": "Minutes", "url": "stream/71-minutes.pdf"},
                    {"type": "Agenda", "name": "Agenda", "url": "stream/71-agenda.pdf"},
                ],
            }
        ]
    }

    first_enumerated = provider.enumerate_meetings(
        source=source,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch_with_payload(first_payload),
    )
    first_result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=first_enumerated,
        synced_at="2026-03-10T20:00:00Z",
    )

    second_enumerated = provider.enumerate_meetings(
        source=source,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch_with_payload(second_payload),
    )
    second_result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=second_enumerated,
        synced_at="2026-03-11T20:00:00Z",
    )

    assert [item.identity.source_meeting_id for item in first_enumerated] == ["71"]
    assert [item.identity.source_meeting_id for item in second_enumerated] == ["71"]
    assert first_result.diagnostics[0].outcome == "accepted"
    assert second_result.diagnostics[0].outcome == "metadata_refreshed"

    repository = DiscoveredMeetingRepository(connection)
    rows = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
    assert len(rows) == 1
    assert rows[0].source_meeting_id == "71"
    assert rows[0].title == "City Council Regular Session"
    assert rows[0].meeting_date == "2026-03-11"
    assert rows[0].source_url == "https://eaglemountainut.portal.civicclerk.com/event/71/files"


def test_sparse_provider_parsing_preserves_identity_through_reconciliation(
    connection: sqlite3.Connection,
) -> None:
    provider = CivicClerkSourceMeetingEnumerationProvider()
    source = _build_source()
    sparse_payload = {
        "value": [
            {
                "id": 88,
                "eventName": "City Council Special Session",
                "publishedFiles": [],
            }
        ]
    }

    enumerated = provider.enumerate_meetings(
        source=source,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch_with_payload(sparse_payload),
    )
    sync_result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=enumerated,
        synced_at="2026-03-10T20:00:00Z",
    )

    _insert_meeting_with_ingest_metadata(
        connection,
        meeting_id="meeting-88",
        meeting_uid="meeting-uid-88",
        metadata={
            "source_url": "https://eaglemountainut.portal.civicclerk.com/",
            "selected_event_id": 88,
        },
    )
    reconcile_result = reconcile_discovered_meetings(
        connection=connection,
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
    )

    assert [item.identity.source_meeting_id for item in enumerated] == ["88"]
    assert enumerated[0].meeting_date is None
    assert enumerated[0].body_name == "City Council"
    assert sync_result.diagnostics[0].outcome == "accepted"
    assert reconcile_result.reconciled_count == 1

    repository = DiscoveredMeetingRepository(connection)
    row = repository.get_by_source_identity(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        source_meeting_id="88",
    )
    assert row is not None
    assert row.meeting_id == "meeting-88"