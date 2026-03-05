from __future__ import annotations

import sqlite3


PILOT_CITY_ID = "city-eagle-mountain-ut"
PILOT_CITY_SOURCE_ID = "source-eagle-mountain-ut-minutes-primary"


def seed_city_registry(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO cities (
                id,
                slug,
                name,
                state_code,
                timezone,
                enabled,
                priority_tier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug = excluded.slug,
                name = excluded.name,
                state_code = excluded.state_code,
                timezone = excluded.timezone,
                enabled = excluded.enabled,
                priority_tier = excluded.priority_tier,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                PILOT_CITY_ID,
                "eagle-mountain-ut",
                "Eagle Mountain",
                "UT",
                "America/Denver",
                1,
                1,
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
            ON CONFLICT(id) DO UPDATE SET
                city_id = excluded.city_id,
                source_type = excluded.source_type,
                source_url = excluded.source_url,
                enabled = excluded.enabled,
                parser_name = excluded.parser_name,
                parser_version = excluded.parser_version,
                health_status = excluded.health_status,
                failure_streak = excluded.failure_streak,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                PILOT_CITY_SOURCE_ID,
                PILOT_CITY_ID,
                "minutes",
                "https://eaglemountainut.portal.civicclerk.com/",
                1,
                "civicclerk-events-api",
                "v1",
                "unknown",
                0,
            ),
        )