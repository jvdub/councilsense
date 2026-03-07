from __future__ import annotations

import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime

import pytest

from councilsense.app.notification_fanout import NotificationSubscriptionTarget
from councilsense.app.notification_delivery_worker import (
    NotificationDeliveryWorker,
    NotificationDeliveryWorkerConfig,
)
from councilsense.app.summarization import (
    ClaimEvidencePointer,
    SummarizationOutput,
    SummaryClaim,
    publish_summarization_output,
)
from councilsense.db import (
    MeetingSummaryRepository,
    PILOT_CITY_ID,
    ProcessingRunRepository,
    apply_migrations,
    seed_city_registry,
)


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


def test_publish_to_delivery_end_to_end_is_idempotent_on_worker_rerun(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-fanout-e2e", city_id=PILOT_CITY_ID)

    output = SummarizationOutput.from_sections(
        summary="Published summary",
        key_decisions=["Decision A"],
        key_actions=["Action A"],
        notable_topics=["Topic A"],
    )
    publish_result = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-e2e",
        meeting_id="meeting-fanout-e2e",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="high",
        output=output,
        published_at="2026-02-27T12:10:00+00:00",
        city_id=PILOT_CITY_ID,
        notification_targets=(
            NotificationSubscriptionTarget(
                user_id="user-e2e",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-e2e",
                status="active",
            ),
        ),
    )

    assert publish_result.notification_enqueue is not None
    assert publish_result.notification_enqueue.enqueued_count == 1
    assert publish_result.notification_enqueue.dedupe_conflict_count == 0

    sender_calls = {"count": 0}

    def _sender(_: object) -> None:
        sender_calls["count"] += 1

    worker = NotificationDeliveryWorker(
        connection=connection,
        sender=_sender,
        config=NotificationDeliveryWorkerConfig(claim_batch_size=1),
        now_provider=lambda: datetime(2030, 1, 1, 0, 0, tzinfo=UTC),
    )

    first_run = worker.run_once()
    second_run = worker.run_once()

    assert first_run.claimed_count == 1
    assert first_run.sent_count == 1
    assert second_run.claimed_count == 0
    assert second_run.sent_count == 0
    assert sender_calls["count"] == 1

    outbox_row = connection.execute(
        """
        SELECT status, attempt_count, sent_at, dedupe_key
        FROM notification_outbox
        WHERE meeting_id = ?
        """,
        ("meeting-fanout-e2e",),
    ).fetchone()
    assert outbox_row is not None
    assert outbox_row[0] == "sent"
    assert int(outbox_row[1]) == 1
    assert outbox_row[2] is not None
    assert str(outbox_row[3]).startswith("notif-dedupe-v1:")

    attempt_rows = connection.execute(
        """
        SELECT attempt_number, outcome
        FROM notification_delivery_attempts
        WHERE outbox_id = (
            SELECT id FROM notification_outbox WHERE meeting_id = ?
        )
        ORDER BY attempt_number ASC
        """,
        ("meeting-fanout-e2e",),
    ).fetchall()
    assert attempt_rows == [(1, "success")]


def test_publish_replay_guard_reuses_existing_publication_and_artifacts(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-fanout-guard", city_id=PILOT_CITY_ID)

    run_repository = ProcessingRunRepository(connection)
    run_repository.create_pending_run(
        run_id="run-fanout-guard",
        city_id=PILOT_CITY_ID,
        cycle_id="cycle-fanout-guard",
    )
    publish_outcome = run_repository.upsert_stage_outcome(
        outcome_id="outcome-publish-run-fanout-guard-meeting-fanout-guard",
        run_id="run-fanout-guard",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-fanout-guard",
        stage_name="publish",
        status="failed",
        metadata_json='{"source_id":"bundle-source"}',
        started_at=None,
        finished_at=None,
    )

    output = SummarizationOutput.from_sections(
        summary="Published summary",
        key_decisions=["Decision A"],
        key_actions=["Action A"],
        notable_topics=["Topic A"],
        claims=(
            SummaryClaim(
                claim_text="Claim A",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact-1",
                        section_ref="minutes:1",
                        char_start=None,
                        char_end=None,
                        excerpt="Evidence A",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )

    first = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-guard-v1",
        meeting_id="meeting-fanout-guard",
        processing_run_id="run-fanout-guard",
        publish_stage_outcome_id=publish_outcome.id,
        version_no=1,
        base_confidence_label="high",
        output=output,
        published_at="2026-03-07T12:00:00Z",
        city_id=PILOT_CITY_ID,
    )
    second = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-fanout-guard-v2",
        meeting_id="meeting-fanout-guard",
        processing_run_id="run-fanout-guard",
        publish_stage_outcome_id=publish_outcome.id,
        version_no=2,
        base_confidence_label="high",
        output=output,
        published_at="2026-03-07T12:05:00Z",
        city_id=PILOT_CITY_ID,
    )

    assert first.publication.id == "pub-fanout-guard-v1"
    assert second.publication.id == first.publication.id
    assert second.replay_guard_reason_code == "publish_stage_outcome_already_materialized"
    assert second.notification_enqueue is None

    publication_count = connection.execute(
        "SELECT COUNT(*) FROM summary_publications WHERE publish_stage_outcome_id = ?",
        (publish_outcome.id,),
    ).fetchone()
    assert publication_count is not None
    assert int(publication_count[0]) == 1

    claim_count = connection.execute(
        "SELECT COUNT(*) FROM publication_claims WHERE publication_id = ?",
        (first.publication.id,),
    ).fetchone()
    assert claim_count is not None
    assert int(claim_count[0]) == 1

    pointer_count = connection.execute(
        "SELECT COUNT(*) FROM claim_evidence_pointers WHERE claim_id = ?",
        (f"{first.publication.id}:claim:1",),
    ).fetchone()
    assert pointer_count is not None
    assert int(pointer_count[0]) == 1
