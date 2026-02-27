from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
    ConfiguredCitySelectionService,
    CityRegistryRepository,
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


def _service(connection: sqlite3.Connection) -> ConfiguredCitySelectionService:
    return ConfiguredCitySelectionService(CityRegistryRepository(connection))


def test_list_enabled_cities_returns_seeded_city_without_any_user_rows(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    service = _service(connection)
    enabled_cities = service.list_enabled_cities()

    assert len(enabled_cities) == 1
    assert enabled_cities[0].id == PILOT_CITY_ID
    assert enabled_cities[0].slug == "eagle-mountain-ut"


def test_list_enabled_city_configs_includes_source_metadata_per_enabled_city(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-second",
            "second-city-ut",
            "Second City",
            "UT",
            "America/Denver",
            1,
            2,
        ),
    )
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
            "source-second-agenda",
            "city-second",
            "agenda",
            "https://example.gov/agenda",
            1,
            "agenda-parser",
            "v2",
            "healthy",
            1,
        ),
    )

    service = _service(connection)
    configs = service.list_enabled_city_configs()

    assert [config.city.id for config in configs] == [PILOT_CITY_ID, "city-second"]
    assert len(configs[0].sources) == 1
    assert configs[0].sources[0].id == PILOT_CITY_SOURCE_ID
    assert configs[0].sources[0].parser_name == "civicplus-minutes-html"
    assert configs[0].sources[0].parser_version == "v1"
    assert configs[1].sources == (
        type(configs[1].sources[0])(
            id="source-second-agenda",
            city_id="city-second",
            source_type="agenda",
            source_url="https://example.gov/agenda",
            parser_name="agenda-parser",
            parser_version="v2",
            health_status="healthy",
            last_success_at=None,
            last_attempt_at=None,
            failure_streak=1,
        ),
    )


def test_disabled_city_and_source_are_excluded_consistently(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        "UPDATE city_sources SET enabled = 0 WHERE id = ?",
        (PILOT_CITY_SOURCE_ID,),
    )
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
            3,
        ),
    )
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
            "source-disabled-city-minutes",
            "city-disabled",
            "minutes",
            "https://disabled.example.gov/minutes",
            1,
            "minutes-parser",
            "v1",
            "unknown",
            0,
        ),
    )

    service = _service(connection)

    assert service.list_enabled_city_ids() == (PILOT_CITY_ID,)
    assert service.list_enabled_sources_for_city(PILOT_CITY_ID) == ()
    assert service.list_enabled_sources_for_city("city-disabled") == ()