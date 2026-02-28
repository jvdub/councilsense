from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
    InvalidMeetingCityError,
    MeetingWriteRepository,
    MissingMeetingCityError,
    PILOT_CITY_ID,
    apply_migrations,
    seed_city_registry,
)


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _repository(connection: sqlite3.Connection) -> MeetingWriteRepository:
    return MeetingWriteRepository(connection)


def test_upsert_meeting_fails_when_city_id_is_missing(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = _repository(connection)

    with pytest.raises(MissingMeetingCityError):
        repository.upsert_meeting(
            meeting_id="meeting-1",
            meeting_uid="uid-1",
            city_id=None,
            title="Regular Session",
        )

    with pytest.raises(MissingMeetingCityError):
        repository.upsert_meeting(
            meeting_id="meeting-2",
            meeting_uid="uid-2",
            city_id="  ",
            title="Work Session",
        )


def test_upsert_meeting_fails_when_city_id_is_unknown_or_disabled(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-disabled",
            "disabled-city-ut",
            "Disabled City",
            "UT",
            "America/Denver",
            0,
            50,
        ),
    )

    repository = _repository(connection)

    with pytest.raises(InvalidMeetingCityError):
        repository.upsert_meeting(
            meeting_id="meeting-unknown",
            meeting_uid="uid-unknown",
            city_id="city-missing",
            title="Unknown City Meeting",
        )

    with pytest.raises(InvalidMeetingCityError):
        repository.upsert_meeting(
            meeting_id="meeting-disabled",
            meeting_uid="uid-disabled",
            city_id="city-disabled",
            title="Disabled City Meeting",
        )


def test_upsert_meeting_succeeds_with_enabled_city_and_preserves_city_linkage(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = _repository(connection)
    persisted = repository.upsert_meeting(
        meeting_id="meeting-1",
        meeting_uid="uid-1",
        city_id=PILOT_CITY_ID,
        title="Regular Session",
    )

    assert persisted.city_id == PILOT_CITY_ID

    persisted_again = repository.upsert_meeting(
        meeting_id="meeting-2",
        meeting_uid="uid-1",
        city_id=PILOT_CITY_ID,
        title="Regular Session (Updated)",
    )
    assert persisted_again.city_id == PILOT_CITY_ID
    assert persisted_again.title == "Regular Session (Updated)"

    rows = connection.execute(
        "SELECT city_id, meeting_uid, title FROM meetings WHERE meeting_uid = ?",
        ("uid-1",),
    ).fetchall()
    assert rows == [(PILOT_CITY_ID, "uid-1", "Regular Session (Updated)")]


def test_database_constraints_also_reject_missing_or_invalid_city_linkage(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO meetings (id, city_id, meeting_uid, title)
            VALUES (?, ?, ?, ?)
            """,
            ("meeting-raw-null", None, "uid-raw-null", "Raw Insert Null City"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO meetings (id, city_id, meeting_uid, title)
            VALUES (?, ?, ?, ?)
            """,
            ("meeting-raw-unknown", "city-missing", "uid-raw-unknown", "Raw Insert Unknown City"),
        )