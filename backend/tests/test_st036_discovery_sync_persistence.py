from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pytest

from councilsense.app.discovery_sync import reconcile_discovered_meetings, sync_enumerated_meetings
from councilsense.app.provider_enumeration import EnumeratedMeeting
from councilsense.db import (
    DiscoveredMeetingIdentity,
    DiscoveredMeetingRepository,
    PILOT_CITY_AGENDA_SOURCE_ID,
    PILOT_CITY_ID,
    PILOT_CITY_SOURCE_ID,
    apply_migrations,
    seed_city_registry,
)


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


def _create_enumerated_meeting(
    *,
    source_meeting_id: str,
    city_source_id: str = PILOT_CITY_SOURCE_ID,
    title: str = "Regular Meeting",
    meeting_date: str | None = "2026-03-09",
    body_name: str | None = "City Council",
    source_url: str | None = None,
) -> EnumeratedMeeting:
    normalized_source_url = source_url or f"https://eaglemountainut.portal.civicclerk.com/event/{source_meeting_id}/files"
    return EnumeratedMeeting(
        identity=DiscoveredMeetingIdentity(
            city_id=PILOT_CITY_ID,
            city_source_id=city_source_id,
            provider_name="civicclerk",
            source_meeting_id=source_meeting_id,
        ),
        title=title,
        meeting_date=meeting_date,
        body_name=body_name,
        source_url=normalized_source_url,
        provider_metadata={"selected_event_id": source_meeting_id},
        raw_payload={"id": source_meeting_id},
    )


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


def test_sync_enumerated_meetings_persists_discovered_meetings(
    connection: sqlite3.Connection,
) -> None:
    enumerated = (
        _create_enumerated_meeting(source_meeting_id="27482", title="Planning Commission", meeting_date="2026-03-10"),
        _create_enumerated_meeting(source_meeting_id="27481", title="Regular Meeting", meeting_date="2026-03-09"),
    )

    result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=enumerated,
        synced_at="2026-03-10T20:00:00Z",
    )

    assert result.synced_count == 2
    assert result.reconciled_count == 0
    assert result.errors == ()

    repository = DiscoveredMeetingRepository(connection)
    retrieved = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
    assert [item.source_meeting_id for item in retrieved] == ["27482", "27481"]
    assert [item.title for item in retrieved] == ["Planning Commission", "Regular Meeting"]


def test_sync_enumerated_meetings_is_idempotent_for_metadata_refresh(
    connection: sqlite3.Connection,
) -> None:
    first = (_create_enumerated_meeting(source_meeting_id="27481", title="Regular Meeting"),)
    second = (
        _create_enumerated_meeting(
            source_meeting_id="27481",
            title="Regular Session and Work Meeting",
            meeting_date="2026-03-10",
            body_name="Council Chambers",
            source_url="https://eaglemountainut.portal.civicclerk.com/event/27481/files/",
        ),
    )

    first_result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=first,
        synced_at="2026-03-09T20:00:00Z",
    )
    second_result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=second,
        synced_at="2026-03-10T20:00:00Z",
    )

    assert first_result.synced_count == 1
    assert second_result.synced_count == 1

    repository = DiscoveredMeetingRepository(connection)
    retrieved = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
    assert len(retrieved) == 1
    assert retrieved[0].title == "Regular Session and Work Meeting"
    assert retrieved[0].meeting_date == "2026-03-10"
    assert retrieved[0].body_name == "Council Chambers"
    assert retrieved[0].source_url == "https://eaglemountainut.portal.civicclerk.com/event/27481/files"
    assert retrieved[0].synced_at == "2026-03-10T20:00:00Z"


def test_reconcile_discovered_meetings_links_matching_local_meeting(
    connection: sqlite3.Connection,
) -> None:
    _insert_meeting_with_ingest_metadata(
        connection,
        meeting_id="meeting-1",
        meeting_uid="meeting-uid-1",
        metadata={
            "selected_event_id": 27481,
            "source_meeting_url": "https://eaglemountainut.portal.civicclerk.com/event/27481/files",
        },
    )
    sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(_create_enumerated_meeting(source_meeting_id="27481"),),
        synced_at="2026-03-10T20:00:00Z",
    )

    result = reconcile_discovered_meetings(
        connection=connection,
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
    )

    assert result.synced_count == 0
    assert result.reconciled_count == 1
    assert result.errors == ()

    repository = DiscoveredMeetingRepository(connection)
    linked = repository.get_by_source_identity(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        source_meeting_id="27481",
    )
    assert linked is not None
    assert linked.meeting_id == "meeting-1"


def test_reconcile_discovered_meetings_skips_ambiguous_matches(
    connection: sqlite3.Connection,
) -> None:
    _insert_meeting_with_ingest_metadata(
        connection,
        meeting_id="meeting-1",
        meeting_uid="meeting-uid-1",
        metadata={"selected_event_id": 27481},
    )
    _insert_meeting_with_ingest_metadata(
        connection,
        meeting_id="meeting-2",
        meeting_uid="meeting-uid-2",
        metadata={"selected_event_id": 27481},
    )
    sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(_create_enumerated_meeting(source_meeting_id="27481"),),
        synced_at="2026-03-10T20:00:00Z",
    )

    result = reconcile_discovered_meetings(
        connection=connection,
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
    )

    assert result.reconciled_count == 0
    assert result.errors == ()

    repository = DiscoveredMeetingRepository(connection)
    linked = repository.get_by_source_identity(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        source_meeting_id="27481",
    )
    assert linked is not None
    assert linked.meeting_id is None


def test_sync_enumerated_meetings_allows_agenda_only_future_event_when_minutes_do_not_exist(
    connection: sqlite3.Connection,
) -> None:
    result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(
            _create_enumerated_meeting(
                city_source_id=PILOT_CITY_AGENDA_SOURCE_ID,
                source_meeting_id="27490",
                title="Agenda-backed Future Meeting",
                meeting_date="2026-03-25",
            ),
        ),
        synced_at="2026-03-11T00:00:00Z",
    )

    assert result.synced_count == 1
    repository = DiscoveredMeetingRepository(connection)
    retrieved = repository.list_for_source(city_source_id=PILOT_CITY_AGENDA_SOURCE_ID)
    assert [item.source_meeting_id for item in retrieved] == ["27490"]


def test_sync_enumerated_meetings_suppresses_agenda_duplicate_when_minutes_event_exists(
    connection: sqlite3.Connection,
) -> None:
    sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(
            _create_enumerated_meeting(
                city_source_id=PILOT_CITY_SOURCE_ID,
                source_meeting_id="27481",
                title="Minutes-backed Meeting",
            ),
        ),
        synced_at="2026-03-10T20:00:00Z",
    )

    result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(
            _create_enumerated_meeting(
                city_source_id=PILOT_CITY_AGENDA_SOURCE_ID,
                source_meeting_id="27481",
                title="Agenda Mirror",
            ),
        ),
        synced_at="2026-03-11T00:00:00Z",
    )

    assert result.synced_count == 1
    assert result.diagnostics[0].outcome == "duplicate_suppressed"
    repository = DiscoveredMeetingRepository(connection)
    assert repository.list_for_source(city_source_id=PILOT_CITY_AGENDA_SOURCE_ID) == ()


def test_sync_enumerated_meetings_removes_existing_agenda_duplicate_when_minutes_arrive(
    connection: sqlite3.Connection,
) -> None:
    sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(
            _create_enumerated_meeting(
                city_source_id=PILOT_CITY_AGENDA_SOURCE_ID,
                source_meeting_id="27481",
                title="Agenda Mirror",
            ),
        ),
        synced_at="2026-03-10T20:00:00Z",
    )

    result = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=(
            _create_enumerated_meeting(
                city_source_id=PILOT_CITY_SOURCE_ID,
                source_meeting_id="27481",
                title="Minutes-backed Meeting",
            ),
        ),
        synced_at="2026-03-11T00:00:00Z",
    )

    assert result.synced_count == 1
    assert "removed 1 supplemental duplicate" in result.diagnostics[0].detail
    repository = DiscoveredMeetingRepository(connection)
    assert repository.list_for_source(city_source_id=PILOT_CITY_AGENDA_SOURCE_ID) == ()
    retrieved = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
    assert [item.source_meeting_id for item in retrieved] == ["27481"]