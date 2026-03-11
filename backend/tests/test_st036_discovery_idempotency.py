from __future__ import annotations

import sqlite3
import tempfile
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from councilsense.app.discovery_sync import (
    build_discovery_sync_dedupe_key,
    reconcile_discovered_meetings,
    sync_enumerated_meetings,
)
from councilsense.app.provider_enumeration import EnumeratedMeeting
from councilsense.db import (
    DiscoveredMeetingIdentity,
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


def _create_enumerated_meeting(
    *,
    source_meeting_id: str,
    title: str = "Regular Meeting",
    meeting_date: str | None = "2026-03-09",
    body_name: str | None = "City Council",
    source_url: str | None = None,
) -> EnumeratedMeeting:
    normalized_source_url = source_url or f"https://eaglemountainut.portal.civicclerk.com/event/{source_meeting_id}/files"
    return EnumeratedMeeting(
        identity=DiscoveredMeetingIdentity(
            city_id=PILOT_CITY_ID,
            city_source_id=PILOT_CITY_SOURCE_ID,
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


def test_discovery_dedupe_key_is_stable_for_source_identity() -> None:
    first = build_discovery_sync_dedupe_key(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name=" CivicClerk ",
        source_meeting_id="27481",
    )
    second = build_discovery_sync_dedupe_key(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="27481",
    )
    different = build_discovery_sync_dedupe_key(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        provider_name="civicclerk",
        source_meeting_id="27482",
    )

    assert first == second
    assert first != different


def test_sync_enumerated_meetings_emits_duplicate_suppressed_diagnostic(
    connection: sqlite3.Connection,
) -> None:
    enumerated = (_create_enumerated_meeting(source_meeting_id="27481"),)

    first = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=enumerated,
        synced_at="2026-03-10T20:00:00Z",
    )
    second = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=enumerated,
        synced_at="2026-03-10T20:00:00Z",
    )

    assert first.diagnostics[0].outcome == "accepted"
    assert second.diagnostics[0].outcome == "duplicate_suppressed"
    assert second.diagnostics[0].code == "discovered_meeting_sync_duplicate_suppressed"

    repository = DiscoveredMeetingRepository(connection)
    rows = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
    assert len(rows) == 1


def test_sync_enumerated_meetings_emits_metadata_refresh_diagnostic(
    connection: sqlite3.Connection,
) -> None:
    first = (_create_enumerated_meeting(source_meeting_id="27481", title="Regular Meeting"),)
    second = (
        _create_enumerated_meeting(
            source_meeting_id="27481",
            title="Regular Session and Work Meeting",
            meeting_date="2026-03-10",
        ),
    )

    sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=first,
        synced_at="2026-03-09T20:00:00Z",
    )
    refreshed = sync_enumerated_meetings(
        connection=connection,
        enumerated_meetings=second,
        synced_at="2026-03-10T20:00:00Z",
    )

    assert refreshed.diagnostics[0].outcome == "metadata_refreshed"
    assert refreshed.diagnostics[0].code == "discovered_meeting_sync_metadata_refreshed"

    repository = DiscoveredMeetingRepository(connection)
    row = repository.get_by_source_identity(
        city_id=PILOT_CITY_ID,
        city_source_id=PILOT_CITY_SOURCE_ID,
        source_meeting_id="27481",
    )
    assert row is not None
    assert row.title == "Regular Session and Work Meeting"
    assert row.meeting_date == "2026-03-10"


def test_concurrent_discovery_writes_converge_on_single_canonical_row() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "discovery-sync.sqlite"
        setup_connection = sqlite3.connect(database_path)
        setup_connection.execute("PRAGMA foreign_keys = ON")
        setup_connection.execute("PRAGMA journal_mode = WAL")
        apply_migrations(setup_connection)
        seed_city_registry(setup_connection)
        setup_connection.close()

        barrier = threading.Barrier(3)
        outcomes: list[str] = []
        failures: list[str] = []
        lock = threading.Lock()

        def _worker() -> None:
            connection = sqlite3.connect(database_path, timeout=5.0)
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                barrier.wait(timeout=5.0)
                result = sync_enumerated_meetings(
                    connection=connection,
                    enumerated_meetings=(_create_enumerated_meeting(source_meeting_id="27481"),),
                    synced_at="2026-03-10T20:00:00Z",
                )
                with lock:
                    outcomes.append(result.diagnostics[0].outcome)
            except Exception as exc:
                with lock:
                    failures.append(str(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5.0)
        for thread in threads:
            thread.join(timeout=5.0)

        assert failures == []
        assert sorted(outcomes) == ["accepted", "duplicate_suppressed"]

        verify_connection = sqlite3.connect(database_path)
        verify_connection.execute("PRAGMA foreign_keys = ON")
        repository = DiscoveredMeetingRepository(verify_connection)
        rows = repository.list_for_source(city_source_id=PILOT_CITY_SOURCE_ID)
        verify_connection.close()
        assert len(rows) == 1