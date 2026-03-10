from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import (
    DiscoveredMeetingRepository,
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


def _create_source(
    connection: sqlite3.Connection,
    *,
    source_id: str,
    city_id: str,
    source_url: str,
) -> None:
    connection.execute(
        """
        INSERT INTO city_sources (
            id,
            city_id,
            source_type,
            source_url,
            enabled,
            parser_name,
            parser_version,
            health_status,
            failure_streak
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            city_id,
            "minutes",
            source_url,
            1,
            "civicclerk-events-api",
            "v1",
            "unknown",
            0,
        ),
    )


def _create_city(connection: sqlite3.Connection, *, city_id: str) -> None:
    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (city_id, f"{city_id}-slug", f"{city_id} name", "UT", "America/Denver", 1, 10),
    )


def _create_meeting(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    city_id: str,
    meeting_uid: str,
) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, meeting_uid, "Council Meeting"),
    )


def test_discovered_meeting_upsert_uses_stable_source_identity_not_title_or_date(
    connection: sqlite3.Connection,
) -> None:
    repository = DiscoveredMeetingRepository(connection)

    first = repository.upsert_discovered_meeting(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="event-27481",
        title="Regular Meeting",
        meeting_date="2026-03-09T19:00:00Z",
        body_name="City Council",
        source_url="https://example.test/meetings/27481",
        synced_at="2026-03-09T20:00:00Z",
    )

    second = repository.upsert_discovered_meeting(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="event-27481",
        title="Regular Session and Work Meeting",
        meeting_date="2026-03-10T01:00:00Z",
        body_name="Council Chambers",
        source_url="https://example.test/meetings/27481?view=detail",
        synced_at="2026-03-10T02:00:00Z",
    )

    assert second.id == first.id
    assert second.discovered_at == "2026-03-09T20:00:00Z"
    assert second.synced_at == "2026-03-10T02:00:00Z"
    assert second.title == "Regular Session and Work Meeting"
    assert second.meeting_date == "2026-03-10T01:00:00Z"
    assert second.body_name == "Council Chambers"
    assert second.source_url == "https://example.test/meetings/27481?view=detail"
    assert second.meeting_id is None


def test_discovered_meeting_uniqueness_is_scoped_to_city_source(
    connection: sqlite3.Connection,
) -> None:
    _create_source(
        connection,
        source_id="source-eagle-mountain-ut-agenda-secondary",
        city_id=PILOT_CITY_ID,
        source_url="https://example.test/agenda-source",
    )
    repository = DiscoveredMeetingRepository(connection)

    first = repository.upsert_discovered_meeting(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="event-27481",
        title="Regular Meeting",
        meeting_date="2026-03-09T19:00:00Z",
        body_name="City Council",
        source_url="https://example.test/meetings/27481",
        synced_at="2026-03-09T20:00:00Z",
    )
    second = repository.upsert_discovered_meeting(
        city_id=PILOT_CITY_ID,
        city_source_id="source-eagle-mountain-ut-agenda-secondary",
        provider_name="civicclerk",
        source_meeting_id="event-27481",
        title="Agenda Mirror",
        meeting_date="2026-03-09T19:00:00Z",
        body_name="City Council",
        source_url="https://example.test/agenda/27481",
        synced_at="2026-03-09T20:05:00Z",
    )

    assert first.id != second.id
    assert repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID) == (first,)


def test_discovered_meeting_schema_enforces_city_source_and_meeting_linkage(
    connection: sqlite3.Connection,
) -> None:
    _create_city(connection, city_id="city-provo-ut")
    _create_source(
        connection,
        source_id="source-provo-ut-minutes-primary",
        city_id="city-provo-ut",
        source_url="https://provo.example.test/meetings",
    )
    _create_meeting(
        connection,
        meeting_id="meeting-provo-1",
        city_id="city-provo-ut",
        meeting_uid="uid-provo-1",
    )
    repository = DiscoveredMeetingRepository(connection)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert_discovered_meeting(
            city_id=PILOT_CITY_ID,
            city_source_id="source-provo-ut-minutes-primary",
            provider_name="civicclerk",
            source_meeting_id="event-88",
            title="Scoped Wrong Source",
            meeting_date="2026-03-09T19:00:00Z",
            body_name="City Council",
            source_url="https://example.test/meetings/88",
            synced_at="2026-03-09T20:00:00Z",
        )

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert_discovered_meeting(
            city_id=PILOT_CITY_ID,
            city_source_id=PILOT_CITY_SOURCE_ID,
            provider_name="civicclerk",
            source_meeting_id="event-89",
            title="Scoped Wrong Meeting Link",
            meeting_date="2026-03-09T19:00:00Z",
            body_name="City Council",
            source_url="https://example.test/meetings/89",
            synced_at="2026-03-09T20:00:00Z",
            meeting_id="meeting-provo-1",
        )


def test_discovered_meeting_linkage_is_optional_but_can_link_to_local_meeting(
    connection: sqlite3.Connection,
) -> None:
    _create_meeting(
        connection,
        meeting_id="meeting-eagle-mountain-1",
        city_id=PILOT_CITY_ID,
        meeting_uid="uid-eagle-mountain-1",
    )
    repository = DiscoveredMeetingRepository(connection)

    linked = repository.upsert_discovered_meeting(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="event-27482",
        title="Planning Commission",
        meeting_date="2026-03-11T01:00:00Z",
        body_name="Planning Commission",
        source_url="https://example.test/meetings/27482",
        synced_at="2026-03-11T02:00:00Z",
        meeting_id="meeting-eagle-mountain-1",
    )

    assert linked.meeting_id == "meeting-eagle-mountain-1"
    fetched = repository.get_by_source_identity(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        source_meeting_id="event-27482",
    )
    assert fetched == linked