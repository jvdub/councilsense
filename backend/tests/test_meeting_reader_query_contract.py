from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
    MeetingListCursor,
    MeetingReadRepository,
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


def _insert_meeting(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    meeting_uid: str,
    title: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, meeting_uid, title, created_at, created_at),
    )


def _insert_publication(
    connection: sqlite3.Connection,
    *,
    publication_id: str,
    meeting_id: str,
    version_no: int,
    publication_status: str,
    confidence_label: str,
    published_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO summary_publications (
            id,
            meeting_id,
            processing_run_id,
            publish_stage_outcome_id,
            version_no,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            meeting_id,
            None,
            None,
            version_no,
            publication_status,
            confidence_label,
            "Summary",
            "[]",
            "[]",
            "[]",
            published_at,
            published_at,
        ),
    )


def test_city_meeting_list_has_deterministic_sort_and_cursor_contract(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    _insert_meeting(
        connection,
        meeting_id="meeting-c",
        meeting_uid="uid-c",
        title="Meeting C",
        created_at="2026-02-20 12:00:00",
    )
    _insert_meeting(
        connection,
        meeting_id="meeting-b",
        meeting_uid="uid-b",
        title="Meeting B",
        created_at="2026-02-20 12:00:00",
    )
    _insert_meeting(
        connection,
        meeting_id="meeting-a",
        meeting_uid="uid-a",
        title="Meeting A",
        created_at="2026-02-19 08:00:00",
    )

    repository = MeetingReadRepository(connection)

    first_page = repository.list_city_meetings(city_id=PILOT_CITY_ID, limit=2)
    assert [item.id for item in first_page.items] == ["meeting-c", "meeting-b"]
    assert first_page.next_cursor is not None

    cursor_token = first_page.next_cursor.to_token()
    parsed_cursor = MeetingListCursor.from_token(cursor_token)
    assert parsed_cursor == MeetingListCursor(created_at="2026-02-20 12:00:00", meeting_id="meeting-b")

    second_page = repository.list_city_meetings(city_id=PILOT_CITY_ID, limit=2, cursor=parsed_cursor)
    assert [item.id for item in second_page.items] == ["meeting-a"]
    assert second_page.next_cursor is None

    repeated_first_page = repository.list_city_meetings(city_id=PILOT_CITY_ID, limit=2)
    assert repeated_first_page == first_page


def test_city_meeting_list_projects_latest_status_and_filters_on_latest_status(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    _insert_meeting(
        connection,
        meeting_id="meeting-3",
        meeting_uid="uid-3",
        title="Meeting 3",
        created_at="2026-02-23 08:00:00",
    )
    _insert_meeting(
        connection,
        meeting_id="meeting-2",
        meeting_uid="uid-2",
        title="Meeting 2",
        created_at="2026-02-22 08:00:00",
    )
    _insert_meeting(
        connection,
        meeting_id="meeting-1",
        meeting_uid="uid-1",
        title="Meeting 1",
        created_at="2026-02-21 08:00:00",
    )

    _insert_publication(
        connection,
        publication_id="pub-1-v1",
        meeting_id="meeting-1",
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        published_at="2026-02-21 10:00:00",
    )
    _insert_publication(
        connection,
        publication_id="pub-1-v2",
        meeting_id="meeting-1",
        version_no=2,
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        published_at="2026-02-21 11:00:00",
    )
    _insert_publication(
        connection,
        publication_id="pub-2-v1",
        meeting_id="meeting-2",
        version_no=1,
        publication_status="processed",
        confidence_label="medium",
        published_at="2026-02-22 10:00:00",
    )

    repository = MeetingReadRepository(connection)
    page = repository.list_city_meetings(city_id=PILOT_CITY_ID, limit=10)

    projected = {
        item.id: (item.publication_status, item.confidence_label)
        for item in page.items
    }
    assert projected["meeting-1"] == ("limited_confidence", "limited_confidence")
    assert projected["meeting-2"] == ("processed", "medium")
    assert projected["meeting-3"] == (None, None)

    processed_only = repository.list_city_meetings(
        city_id=PILOT_CITY_ID,
        limit=10,
        publication_status="processed",
    )
    assert [item.id for item in processed_only.items] == ["meeting-2"]


def test_city_meeting_list_query_path_uses_expected_indexes(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    _insert_meeting(
        connection,
        meeting_id="meeting-index",
        meeting_uid="uid-index",
        title="Indexed Meeting",
        created_at="2026-02-24 09:00:00",
    )
    _insert_publication(
        connection,
        publication_id="pub-index-v1",
        meeting_id="meeting-index",
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        published_at="2026-02-24 09:05:00",
    )

    repository = MeetingReadRepository(connection)
    plan = repository.explain_city_meetings_query_plan(
        city_id=PILOT_CITY_ID,
        limit=5,
        publication_status="processed",
    )
    plan_text = "\n".join(plan)

    assert "idx_meetings_city_created_id" in plan_text
    assert "idx_summary_publications_meeting_published_id" in plan_text
