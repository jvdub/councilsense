from __future__ import annotations

import json
import sqlite3

import pytest

from councilsense.app.pipeline_retry import (
    PermanentStageError,
    StageExecutionService,
    StageRetryPolicy,
    StageWorkItem,
    TransientStageError,
)
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
    )

    state = {"attempts": 0}

    def _worker(_: StageWorkItem) -> None:
        state["attempts"] += 1
        if state["attempts"] < 3:
            raise TransientStageError("upstream timeout")

    result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)

    assert result.status == "processed"
    assert result.attempts == 3
    assert state["attempts"] == 3
    assert repository.get_run(run_id=run.id).status == "processed"

    outcomes = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)
    assert [outcome.status for outcome in outcomes] == ["processed"]
    metadata = json.loads(outcomes[0].metadata_json or "{}")
    assert metadata["attempts"] == 3
    assert metadata["failure_classification"] is None


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
    )

    state = {"attempts": 0}

    def _worker(_: StageWorkItem) -> None:
        state["attempts"] += 1
        raise PermanentStageError("unsupported payload")

    result = execution.execute_one(stage_name="extract", item=item, worker=_worker)

    assert result.status == "failed"
    assert result.failure_classification == "permanent"
    assert result.attempts == 1
    assert state["attempts"] == 1
    assert repository.get_run(run_id=run.id).status == "failed"

    outcomes = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)
    assert [outcome.status for outcome in outcomes] == ["failed"]
    metadata = json.loads(outcomes[0].metadata_json or "{}")
    assert metadata["attempts"] == 1
    assert metadata["failure_classification"] == "permanent"


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
