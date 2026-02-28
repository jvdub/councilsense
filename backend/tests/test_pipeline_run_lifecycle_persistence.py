from __future__ import annotations

import sqlite3

import pytest

from councilsense.app.scheduler import InMemoryCityScanQueueProducer, run_scheduler_cycle
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_run_lifecycle_status_transitions_persist_started_and_finished_timestamps(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    service = ProcessingLifecycleService(repository)

    created = repository.create_pending_run(
        run_id="run-lifecycle-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T03:00:00Z",
    )
    assert created.status == "pending"
    assert created.started_at is not None
    assert created.finished_at is None

    completed = service.mark_processed(run_id=created.id)
    assert completed.status == "processed"
    assert completed.started_at is not None
    assert completed.finished_at is not None


def test_stage_outcomes_are_queryable_by_run_and_city(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    run = repository.create_pending_run(
        run_id="run-lifecycle-2",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T04:00:00Z",
    )

    ingest_outcome = repository.upsert_stage_outcome(
        outcome_id="outcome-ingest-1",
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-77",
        stage_name="ingest",
        status="processed",
        metadata_json='{"source":"agenda-feed"}',
        started_at="2026-02-27T04:00:01Z",
        finished_at="2026-02-27T04:00:09Z",
    )
    summarize_outcome = repository.upsert_stage_outcome(
        outcome_id="outcome-summarize-1",
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-77",
        stage_name="summarize",
        status="limited_confidence",
        metadata_json='{"score":0.62}',
        started_at="2026-02-27T04:00:10Z",
        finished_at="2026-02-27T04:00:20Z",
    )

    outcomes = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)

    assert [outcome.stage_name for outcome in outcomes] == ["ingest", "summarize"]
    assert outcomes == (
        ingest_outcome,
        summarize_outcome,
    )


def test_scheduler_enqueue_to_completion_and_failure_persists_lifecycle_records(
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
            "source-second-minutes-primary",
            "city-second",
            "minutes",
            "https://second-city.ut/minutes",
            1,
            "second-minutes-parser",
            "v2",
            "unknown",
            0,
        ),
    )

    queue = InMemoryCityScanQueueProducer()
    enqueued_city_ids = run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T05:00:00Z",
    )
    assert enqueued_city_ids == (PILOT_CITY_ID, "city-second")

    repository = ProcessingRunRepository(connection)
    service = ProcessingLifecycleService(repository)

    first_action = queue.enqueued_actions[0]
    second_action = queue.enqueued_actions[1]

    repository.upsert_stage_outcome(
        outcome_id="outcome-processed-1",
        run_id=first_action.run_id,
        city_id=first_action.city_id,
        meeting_id="meeting-success",
        stage_name="publish",
        status="processed",
        metadata_json='{"records":1}',
        started_at="2026-02-27T05:01:00Z",
        finished_at="2026-02-27T05:01:10Z",
    )
    repository.upsert_stage_outcome(
        outcome_id="outcome-failed-1",
        run_id=second_action.run_id,
        city_id=second_action.city_id,
        meeting_id="meeting-failure",
        stage_name="extract",
        status="failed",
        metadata_json='{"error":"timeout"}',
        started_at="2026-02-27T05:01:00Z",
        finished_at="2026-02-27T05:01:30Z",
    )

    processed_run = service.mark_processed(run_id=first_action.run_id)
    failed_run = service.mark_failed(run_id=second_action.run_id)

    assert processed_run.status == "processed"
    assert failed_run.status == "failed"
    assert processed_run.parser_version == "civicplus-minutes-html@v1"
    assert failed_run.parser_version == "second-minutes-parser@v2"
    assert processed_run.source_version.startswith("sources-sha256:")
    assert failed_run.source_version.startswith("sources-sha256:")
    assert processed_run.finished_at is not None
    assert failed_run.finished_at is not None

    processed_outcomes = repository.list_stage_outcomes_for_run_city(
        run_id=first_action.run_id,
        city_id=first_action.city_id,
    )
    failed_outcomes = repository.list_stage_outcomes_for_run_city(
        run_id=second_action.run_id,
        city_id=second_action.city_id,
    )

    assert [outcome.status for outcome in processed_outcomes] == ["processed"]
    assert [outcome.status for outcome in failed_outcomes] == ["failed"]
