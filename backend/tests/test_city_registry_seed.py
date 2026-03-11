from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
    PILOT_CITY_AGENDA_SOURCE_ID,
    PILOT_CITY_ID,
    PILOT_CITY_SOURCE_ID,
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


def test_seed_city_registry_creates_pilot_records_and_is_idempotent(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)

    seed_city_registry(connection)
    seed_city_registry(connection)

    city_count = connection.execute(
        "SELECT COUNT(*) FROM cities WHERE id = ?",
        (PILOT_CITY_ID,),
    ).fetchone()
    source_count = connection.execute(
        "SELECT COUNT(*) FROM city_sources WHERE city_id = ?",
        (PILOT_CITY_ID,),
    ).fetchone()

    assert city_count == (1,)
    assert source_count == (2,)

    joined = connection.execute(
        """
        SELECT c.slug, c.enabled, cs.source_type, cs.enabled, cs.parser_name, cs.parser_version
        FROM cities c
        JOIN city_sources cs ON cs.city_id = c.id
        WHERE c.id = ?
        ORDER BY cs.source_type ASC, cs.id ASC
        """,
        (PILOT_CITY_ID,),
    ).fetchall()
    assert joined == [
        ("eagle-mountain-ut", 1, "agenda", 1, "civicclerk-events-api", "v1"),
        ("eagle-mountain-ut", 1, "minutes", 1, "civicclerk-events-api", "v1"),
    ]


def test_seed_city_registry_reapplies_canonical_defaults(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        "UPDATE cities SET enabled = 0, priority_tier = 50 WHERE id = ?",
        (PILOT_CITY_ID,),
    )
    connection.execute(
        """
        UPDATE city_sources
        SET enabled = 0, parser_version = 'legacy', health_status = 'degraded', failure_streak = 3
        WHERE id IN (?, ?)
        """,
        (PILOT_CITY_SOURCE_ID, PILOT_CITY_AGENDA_SOURCE_ID),
    )

    seed_city_registry(connection)

    city = connection.execute(
        "SELECT enabled, priority_tier FROM cities WHERE id = ?",
        (PILOT_CITY_ID,),
    ).fetchone()
    source = connection.execute(
        """
        SELECT id, enabled, parser_version, health_status, failure_streak
        FROM city_sources
        WHERE id IN (?, ?)
        ORDER BY id ASC
        """,
        (PILOT_CITY_SOURCE_ID, PILOT_CITY_AGENDA_SOURCE_ID),
    ).fetchall()

    assert city == (1, 1)
    assert source == [
        (PILOT_CITY_AGENDA_SOURCE_ID, 1, "v1", "unknown", 0),
        (PILOT_CITY_SOURCE_ID, 1, "v1", "unknown", 0),
    ]