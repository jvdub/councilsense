from __future__ import annotations

import json
import sqlite3

import pytest

from councilsense.app.pipeline_retry import (
    PIPELINE_RETRY_POLICY_VERSION,
    PermanentStageError,
    StageExecutionService,
    StageRetryPolicy,
    StageWorkItem,
    TransientStageError,
)
from councilsense.app.scheduler import InMemoryCityScanQueueProducer, run_scheduler_cycle
from councilsense.db import (
    PILOT_CITY_ID,
    PILOT_CITY_SOURCE_ID,
    ProcessingLifecycleService,
    ProcessingRunRepository,
    SourceHealthRepository,
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


def test_transient_failure_retries_until_success(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-retry-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T06:00:00Z",
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-retry-success",
        source_id="source-agenda",
        source_type="agenda",
    )

    state = {"attempts": 0}

    def _worker(_: StageWorkItem) -> None:
        state["attempts"] += 1
        if state["attempts"] < 3:
            raise TransientStageError("upstream timeout")

    result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)

    assert result.status == "processed"
    assert result.attempts == 3
    assert result.max_attempts == 3
    assert result.final_disposition == "success"
    assert result.retry_policy_version == PIPELINE_RETRY_POLICY_VERSION
    assert state["attempts"] == 3
    assert repository.get_run(run_id=run.id).status == "processed"

    outcomes = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)
    assert [outcome.status for outcome in outcomes] == ["processed"]
    metadata = json.loads(outcomes[0].metadata_json or "{}")
    assert metadata["attempts"] == 3
    assert metadata["failure_classification"] is None
    assert metadata["final_disposition"] == "success"
    assert metadata["retry_policy_version"] == PIPELINE_RETRY_POLICY_VERSION
    assert metadata["policy_key"] == "ingest:agenda"
    assert metadata["source_attempts"]["source-agenda"]["attempts"] == 3


def test_permanent_failure_skips_retry_and_marks_failed(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-permanent-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T07:00:00Z",
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=5),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-permanent-failure",
        source_id="source-minutes",
        source_type="minutes",
    )

    state = {"attempts": 0}

    def _worker(_: StageWorkItem) -> None:
        state["attempts"] += 1
        raise PermanentStageError("unsupported payload")

    result = execution.execute_one(stage_name="extract", item=item, worker=_worker)

    assert result.status == "failed"
    assert result.failure_classification == "terminal"
    assert result.attempts == 1
    assert result.max_attempts == 3
    assert result.final_disposition == "terminal"
    assert state["attempts"] == 1
    assert repository.get_run(run_id=run.id).status == "failed"

    outcomes = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)
    assert [outcome.status for outcome in outcomes] == ["failed"]
    metadata = json.loads(outcomes[0].metadata_json or "{}")
    assert metadata["attempts"] == 1
    assert metadata["failure_classification"] == "terminal"
    assert metadata["final_disposition"] == "terminal"
    assert metadata["terminal_reason"] == "non_retryable"
    assert metadata["policy_key"] == "extract:minutes"


def test_city_failure_does_not_block_other_city_runs(connection: sqlite3.Connection) -> None:
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

    queue = InMemoryCityScanQueueProducer()
    run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T08:00:00Z",
    )

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )

    items = tuple(
        StageWorkItem(
            run_id=action.run_id,
            city_id=action.city_id,
            meeting_id=f"meeting-{action.city_id}",
            source_id="source-city-feed",
            source_type="minutes",
        )
        for action in queue.enqueued_actions
    )

    def _worker(item: StageWorkItem) -> None:
        if item.city_id == "city-second":
            raise PermanentStageError("source parse failed")

    results = execution.execute_many(stage_name="summarize", items=items, worker=_worker)

    assert len(results) == 2
    status_by_city = {result.city_id: result.status for result in results}
    assert status_by_city[PILOT_CITY_ID] == "processed"
    assert status_by_city["city-second"] == "failed"

    run_status_by_city = {
        action.city_id: repository.get_run(run_id=action.run_id).status
        for action in queue.enqueued_actions
    }
    assert run_status_by_city[PILOT_CITY_ID] == "processed"
    assert run_status_by_city["city-second"] == "failed"


def test_ingest_source_health_transitions_from_failure_to_success(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        """
        UPDATE city_sources
        SET
            health_status = 'degraded',
            failure_streak = 2,
            last_failure_at = '2026-02-26T00:00:00Z',
            last_failure_reason = 'PermanentStageError: previous failure'
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    )

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        source_health_repository=SourceHealthRepository(connection),
        retry_policy=StageRetryPolicy(max_attempts=3),
    )
    run = repository.create_pending_run(
        run_id="run-ingest-health-transition",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T11:00:00Z",
    )

    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-health-transition",
        source_id=PILOT_CITY_SOURCE_ID,
        source_type="minutes",
    )

    execution.execute_one(stage_name="ingest", item=item, worker=lambda _: None)

    row = connection.execute(
        """
        SELECT health_status, failure_streak, last_attempt_at, last_success_at, last_failure_at, last_failure_reason
        FROM city_sources
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    ).fetchone()

    assert row is not None
    assert row[0] == "healthy"
    assert row[1] == 0
    assert row[2] is not None
    assert row[3] is not None
    assert row[4] == "2026-02-26T00:00:00Z"
    assert row[5] == "PermanentStageError: previous failure"


def test_ingest_single_source_failure_does_not_block_other_source(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

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
            "source-second-minutes",
            PILOT_CITY_ID,
            "agenda",
            "https://example.gov/agenda-second",
            1,
            "agenda-parser",
            "v1",
            "unknown",
            0,
        ),
    )

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        source_health_repository=SourceHealthRepository(connection),
        retry_policy=StageRetryPolicy(max_attempts=2),
    )

    first_run = repository.create_pending_run(
        run_id="run-ingest-source-one",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T12:00:00Z",
    )
    second_run = repository.create_pending_run(
        run_id="run-ingest-source-two",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T12:01:00Z",
    )

    items = (
        StageWorkItem(
            run_id=first_run.id,
            city_id=PILOT_CITY_ID,
            meeting_id="meeting-source-failed",
            source_id=PILOT_CITY_SOURCE_ID,
            source_type="minutes",
        ),
        StageWorkItem(
            run_id=second_run.id,
            city_id=PILOT_CITY_ID,
            meeting_id="meeting-source-success",
            source_id="source-second-minutes",
            source_type="agenda",
        ),
    )

    def _worker(item: StageWorkItem) -> None:
        if item.source_id == PILOT_CITY_SOURCE_ID:
            raise PermanentStageError("parser mismatch")

    results = execution.execute_many(stage_name="ingest", items=items, worker=_worker)
    result_by_source = {result.source_id: result for result in results}

    assert result_by_source[PILOT_CITY_SOURCE_ID].status == "failed"
    assert result_by_source["source-second-minutes"].status == "processed"

    failed_source = connection.execute(
        """
        SELECT health_status, failure_streak, last_success_at, last_attempt_at, last_failure_at, last_failure_reason
        FROM city_sources
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    ).fetchone()
    healthy_source = connection.execute(
        """
        SELECT health_status, failure_streak, last_success_at, last_attempt_at, last_failure_at, last_failure_reason
        FROM city_sources
        WHERE id = ?
        """,
        ("source-second-minutes",),
    ).fetchone()

    assert failed_source is not None
    assert failed_source[0] == "degraded"
    assert failed_source[1] == 1
    assert failed_source[2] is None
    assert failed_source[3] is not None
    assert failed_source[4] is not None
    assert failed_source[5] == "PermanentStageError: parser mismatch"

    assert healthy_source is not None
    assert healthy_source[0] == "healthy"
    assert healthy_source[1] == 0
    assert healthy_source[2] is not None
    assert healthy_source[3] is not None
    assert healthy_source[4] is None
    assert healthy_source[5] is None
