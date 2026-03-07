from __future__ import annotations

import json
import sqlite3

import pytest

from councilsense.app.pipeline_retry import (
    PIPELINE_RETRY_POLICY_VERSION,
    StageExecutionService,
    StageRetryPolicy,
    StageWorkItem,
    TransientStageError,
    resolve_stage_retry_policy,
)
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_resolve_stage_retry_policy_matrix_by_stage_and_source() -> None:
    assert resolve_stage_retry_policy(stage_name="ingest", source_type="minutes").max_attempts == 4
    assert resolve_stage_retry_policy(stage_name="ingest", source_type="agenda").max_attempts == 3
    assert resolve_stage_retry_policy(stage_name="ingest", source_type="packet").max_attempts == 2
    assert resolve_stage_retry_policy(stage_name="extract", source_type="minutes").max_attempts == 3
    assert resolve_stage_retry_policy(stage_name="summarize", source_type=None).source_type == "bundle"
    assert resolve_stage_retry_policy(stage_name="publish", source_type=None).max_attempts == 3

    clamped = resolve_stage_retry_policy(
        stage_name="ingest",
        source_type="minutes",
        retry_policy=StageRetryPolicy(max_attempts=2),
    )
    assert clamped.max_attempts == 2
    assert clamped.policy_version == PIPELINE_RETRY_POLICY_VERSION
    assert clamped.matrix_key == "ingest:minutes"


def test_transient_minutes_ingest_exhausts_stage_source_cap(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-st029-minutes-cap",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T09:00:00Z",
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=9),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-st029-minutes-cap",
        source_id="source-minutes-cap",
        source_type="minutes",
    )

    attempts = {"count": 0}

    def _worker(_: StageWorkItem) -> None:
        attempts["count"] += 1
        raise LookupError("minutes page not published yet")

    result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)

    assert attempts["count"] == 4
    assert result.status == "failed"
    assert result.attempts == 4
    assert result.max_attempts == 4
    assert result.failure_classification == "transient"
    assert result.final_disposition == "terminal"

    outcome = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)[0]
    metadata = json.loads(outcome.metadata_json or "{}")
    assert metadata["retry_policy_version"] == PIPELINE_RETRY_POLICY_VERSION
    assert metadata["policy_key"] == "ingest:minutes"
    assert metadata["failure_classification"] == "transient"
    assert metadata["final_disposition"] == "terminal"
    assert metadata["terminal_reason"] == "retry_exhausted"
    assert metadata["source_attempts"]["source-minutes-cap"]["attempts"] == 4


def test_attempt_accounting_is_monotonic_across_reruns_for_same_source(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-st029-rerun-attempts",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T09:15:00Z",
    )

    repository.upsert_stage_outcome(
        outcome_id="outcome-ingest-run-st029-rerun-attempts-meeting-rerun",
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-rerun",
        stage_name="ingest",
        status="failed",
        metadata_json=json.dumps(
            {
                "attempts": 1,
                "source_id": "source-rerun",
                "source_type": "agenda",
                "source_attempts": {
                    "source-rerun": {
                        "attempts": 1,
                        "failure_classification": "transient",
                        "final_disposition": "retry",
                        "max_attempts": 3,
                        "policy_key": "ingest:agenda",
                        "retry_policy_version": PIPELINE_RETRY_POLICY_VERSION,
                        "source_id": "source-rerun",
                        "source_type": "agenda",
                        "stage_name": "ingest",
                        "terminal_reason": None,
                        "error_message": "upstream timeout",
                        "error_type": "TransientStageError",
                    }
                },
            },
            sort_keys=True,
        ),
        started_at=None,
        finished_at=None,
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=5),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-rerun",
        source_id="source-rerun",
        source_type="agenda",
    )

    result = execution.execute_one(stage_name="ingest", item=item, worker=lambda _: None)

    assert result.status == "processed"
    assert result.attempts == 2
    assert result.max_attempts == 3

    outcome = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)[0]
    metadata = json.loads(outcome.metadata_json or "{}")
    assert metadata["attempts"] == 2
    assert metadata["source_attempts"]["source-rerun"]["attempts"] == 2
    assert metadata["source_attempts"]["source-rerun"]["final_disposition"] == "success"


def test_stage_metadata_preserves_other_sources_in_same_stage_row(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-st029-source-merge",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T09:30:00Z",
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=5),
    )

    execution.execute_one(
        stage_name="ingest",
        item=StageWorkItem(
            run_id=run.id,
            city_id=run.city_id,
            meeting_id="meeting-source-merge",
            source_id="source-minutes-merge",
            source_type="minutes",
        ),
        worker=lambda _: None,
    )
    execution.execute_one(
        stage_name="ingest",
        item=StageWorkItem(
            run_id=run.id,
            city_id=run.city_id,
            meeting_id="meeting-source-merge",
            source_id="source-agenda-merge",
            source_type="agenda",
        ),
        worker=lambda _: None,
    )

    outcome = repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=run.city_id)[0]
    metadata = json.loads(outcome.metadata_json or "{}")
    assert set(metadata["source_attempts"].keys()) == {"source-minutes-merge", "source-agenda-merge"}
    assert metadata["source_attempts"]["source-minutes-merge"]["policy_key"] == "ingest:minutes"
    assert metadata["source_attempts"]["source-agenda-merge"]["policy_key"] == "ingest:agenda"