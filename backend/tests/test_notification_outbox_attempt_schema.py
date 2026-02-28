from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import apply_migrations


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def seeded_meeting(connection: sqlite3.Connection) -> tuple[str, str]:
    apply_migrations(connection)

    city_id = "city-seattle"
    meeting_id = "meeting-001"

    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (city_id, "seattle-wa", "Seattle", "WA", "America/Los_Angeles", 1, 1),
    )
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, "uid-001", "City Council"),
    )
    return city_id, meeting_id


def test_notification_outbox_enforces_unique_dedupe_key(
    connection: sqlite3.Connection,
    seeded_meeting: tuple[str, str],
) -> None:
    city_id, meeting_id = seeded_meeting

    outbox_row = (
        "outbox-1",
        "user-1",
        meeting_id,
        city_id,
        "meeting_published",
        "notif-dedupe-v1:hash-1",
        '{"meeting_id":"meeting-001"}',
    )

    connection.execute(
        """
        INSERT INTO notification_outbox (
            id,
            user_id,
            meeting_id,
            city_id,
            notification_type,
            dedupe_key,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        outbox_row,
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO notification_outbox (
                id,
                user_id,
                meeting_id,
                city_id,
                notification_type,
                dedupe_key,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "outbox-2",
                "user-1",
                meeting_id,
                city_id,
                "meeting_published",
                "notif-dedupe-v1:hash-1",
                '{"meeting_id":"meeting-001"}',
            ),
        )


def test_notification_attempts_allow_multiple_retries_per_outbox(
    connection: sqlite3.Connection,
    seeded_meeting: tuple[str, str],
) -> None:
    city_id, meeting_id = seeded_meeting

    connection.execute(
        """
        INSERT INTO notification_outbox (
            id,
            user_id,
            meeting_id,
            city_id,
            notification_type,
            dedupe_key,
            payload_json,
            status,
            attempt_count,
            next_retry_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            "outbox-1",
            "user-1",
            meeting_id,
            city_id,
            "meeting_published",
            "notif-dedupe-v1:hash-2",
            '{"meeting_id":"meeting-001"}',
            "failed",
            1,
        ),
    )

    connection.execute(
        """
        INSERT INTO notification_delivery_attempts (
            outbox_id,
            attempt_number,
            outcome,
            error_code,
            provider_response_summary,
            next_retry_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        ("outbox-1", 1, "retryable_failure", "timeout", "provider timeout"),
    )
    connection.execute(
        """
        INSERT INTO notification_delivery_attempts (
            outbox_id,
            attempt_number,
            outcome,
            provider_response_summary
        )
        VALUES (?, ?, ?, ?)
        """,
        ("outbox-1", 2, "success", "ok"),
    )

    attempts = connection.execute(
        """
        SELECT attempt_number, outcome
        FROM notification_delivery_attempts
        WHERE outbox_id = ?
        ORDER BY attempt_number ASC
        """,
        ("outbox-1",),
    ).fetchall()
    assert attempts == [(1, "retryable_failure"), (2, "success")]

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO notification_delivery_attempts (outbox_id, attempt_number, outcome)
            VALUES (?, ?, ?)
            """,
            ("outbox-1", 2, "success"),
        )
