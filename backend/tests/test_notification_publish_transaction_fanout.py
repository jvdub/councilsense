from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.app.notification_fanout import NotificationSubscriptionTarget
from councilsense.app.summarization import SummarizationOutput, publish_summarization_output
from councilsense.db import MeetingSummaryRepository, PILOT_CITY_ID, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str, city_id: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, f"uid-{meeting_id}", "Council Meeting"),
    )


def test_publish_enqueues_outbox_rows_for_eligible_city_active_subscriptions(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-fanout-1", city_id=PILOT_CITY_ID)

    output = SummarizationOutput.from_sections(
        summary="Published summary",
        key_decisions=["Decision A"],
        key_actions=["Action A"],
        notable_topics=["Topic A"],
    )

    result = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-1",
        meeting_id="meeting-fanout-1",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="high",
        output=output,
        published_at="2026-02-27T12:00:00Z",
        city_id=PILOT_CITY_ID,
        notification_targets=(
            NotificationSubscriptionTarget(
                user_id="user-eligible-1",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-eligible-1",
                status="active",
            ),
            NotificationSubscriptionTarget(
                user_id="user-eligible-2",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-eligible-2",
                status="active",
            ),
            NotificationSubscriptionTarget(
                user_id="user-invalid",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-invalid",
                status="invalid",
            ),
            NotificationSubscriptionTarget(
                user_id="user-other-city",
                city_id="city-other",
                subscription_id="sub-other-city",
                status="active",
            ),
        ),
    )

    assert result.notification_enqueue is not None
    assert result.notification_enqueue.eligible_subscription_count == 2
    assert result.notification_enqueue.enqueued_count == 2
    assert result.notification_enqueue.dedupe_conflict_count == 0

    rows = connection.execute(
        """
        SELECT user_id, city_id, meeting_id, notification_type, subscription_id
        FROM notification_outbox
        ORDER BY user_id ASC
        """
    ).fetchall()
    assert rows == [
        ("user-eligible-1", PILOT_CITY_ID, "meeting-fanout-1", "meeting_published", "sub-eligible-1"),
        ("user-eligible-2", PILOT_CITY_ID, "meeting-fanout-1", "meeting_published", "sub-eligible-2"),
    ]


def test_duplicate_publish_trigger_is_idempotent_for_outbox_dedupe(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-fanout-2", city_id=PILOT_CITY_ID)

    output = SummarizationOutput.from_sections(
        summary="Published summary",
        key_decisions=["Decision A"],
        key_actions=["Action A"],
        notable_topics=["Topic A"],
    )
    targets = (
        NotificationSubscriptionTarget(
            user_id="user-1",
            city_id=PILOT_CITY_ID,
            subscription_id="sub-1",
            status="active",
        ),
    )

    first = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-2-v1",
        meeting_id="meeting-fanout-2",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="high",
        output=output,
        published_at="2026-02-27T12:01:00Z",
        city_id=PILOT_CITY_ID,
        notification_targets=targets,
    )
    second = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-2-v2",
        meeting_id="meeting-fanout-2",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=2,
        base_confidence_label="high",
        output=output,
        published_at="2026-02-27T12:02:00Z",
        city_id=PILOT_CITY_ID,
        notification_targets=targets,
    )

    assert first.notification_enqueue is not None
    assert first.notification_enqueue.enqueued_count == 1
    assert first.notification_enqueue.dedupe_conflict_count == 0

    assert second.notification_enqueue is not None
    assert second.notification_enqueue.enqueued_count == 0
    assert second.notification_enqueue.dedupe_conflict_count == 1

    outbox_rows = connection.execute(
        "SELECT count(*) FROM notification_outbox WHERE meeting_id = ?",
        ("meeting-fanout-2",),
    ).fetchone()
    assert outbox_rows is not None
    assert int(outbox_rows[0]) == 1


def test_failed_outbox_write_rolls_back_publish_transaction(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-fanout-3", city_id=PILOT_CITY_ID)

    output = SummarizationOutput.from_sections(
        summary="Published summary",
        key_decisions=["Decision A"],
        key_actions=["Action A"],
        notable_topics=["Topic A"],
    )

    with pytest.raises(sqlite3.IntegrityError):
        publish_summarization_output(
            repository=MeetingSummaryRepository(connection),
            publication_id="pub-fanout-3",
            meeting_id="meeting-fanout-3",
            processing_run_id=None,
            publish_stage_outcome_id=None,
            version_no=1,
            base_confidence_label="high",
            output=output,
            published_at="2026-02-27T12:03:00Z",
            city_id="city-does-not-exist",
            notification_targets=(
                NotificationSubscriptionTarget(
                    user_id="user-1",
                    city_id="city-does-not-exist",
                    subscription_id="sub-1",
                    status="active",
                ),
            ),
        )

    publication_rows = connection.execute(
        "SELECT count(*) FROM summary_publications WHERE id = ?",
        ("pub-fanout-3",),
    ).fetchone()
    assert publication_rows is not None
    assert int(publication_rows[0]) == 0

    outbox_rows = connection.execute(
        "SELECT count(*) FROM notification_outbox WHERE meeting_id = ?",
        ("meeting-fanout-3",),
    ).fetchone()
    assert outbox_rows is not None
    assert int(outbox_rows[0]) == 0
