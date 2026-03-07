from __future__ import annotations

import json
import sqlite3

import pytest

from councilsense.app.pipeline_retry import StageExecutionService, StageRetryPolicy, StageWorkItem, TransientStageError
from councilsense.db import (
    PIPELINE_DLQ_CONTRACT_VERSION,
    PIPELINE_DLQ_STATUS_MODEL,
    PILOT_CITY_ID,
    ProcessingLifecycleService,
    ProcessingRunRepository,
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


def test_terminal_retry_cap_persists_pipeline_dlq_context(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-pipeline-dlq-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T10:00:00Z",
    )

    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=4),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-pipeline-dlq-1",
        source_id="pilot-minutes-source",
        source_type="minutes",
        payload_references={"raw_artifact_uri": "s3://pipeline/raw/meeting-pipeline-dlq-1.json"},
        triage_metadata={"worker_name": "ingest-terminal-test", "failure_scope": "source"},
    )

    def _worker(_: StageWorkItem) -> None:
        raise TransientStageError("upstream minutes fetch timed out")

    result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)

    assert result.status == "failed"
    assert result.failure_classification == "transient"
    assert result.attempts == 4
    assert result.final_disposition == "terminal"

    dlq_records = repository.list_pipeline_dlq_entries(run_id=run.id)
    assert len(dlq_records) == 1
    record = dlq_records[0]
    assert record.contract_version == PIPELINE_DLQ_CONTRACT_VERSION
    assert record.run_id == run.id
    assert record.city_id == run.city_id
    assert record.meeting_id == item.meeting_id
    assert record.stage_name == "ingest"
    assert record.source_id == item.source_id
    assert record.source_type == "minutes"
    assert record.status == "open"
    assert record.failure_classification == "transient"
    assert record.terminal_reason == "retry_exhausted"
    assert record.retry_policy_version == result.retry_policy_version
    assert record.terminal_attempt_number == 4
    assert record.max_attempts == 4
    assert record.error_code == "transient_stage_error"
    assert record.error_type == "TransientStageError"
    assert record.error_message == "upstream minutes fetch timed out"

    payload_references = json.loads(record.payload_references_json)
    assert payload_references == {"raw_artifact_uri": "s3://pipeline/raw/meeting-pipeline-dlq-1.json"}

    triage_metadata = json.loads(record.triage_metadata_json)
    assert triage_metadata["contract_version"] == PIPELINE_DLQ_CONTRACT_VERSION
    assert triage_metadata["worker_name"] == "ingest-terminal-test"
    assert triage_metadata["failure_scope"] == "source"
    assert triage_metadata["policy_key"] == "ingest:minutes"
    assert triage_metadata["terminal_reason"] == "retry_exhausted"
    assert triage_metadata["error_code"] == "transient_stage_error"

    outcome = repository.get_stage_outcome(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id=item.meeting_id,
        stage_name="ingest",
    )
    assert outcome is not None
    outcome_metadata = json.loads(outcome.metadata_json or "{}")
    assert outcome_metadata["payload_references"] == payload_references
    assert outcome_metadata["triage_metadata"]["terminal_reason"] == "retry_exhausted"


def test_pipeline_dlq_insert_is_idempotent_and_rerun_stable(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-pipeline-dlq-2",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T11:00:00Z",
    )
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-pipeline-dlq-2",
        source_id="pilot-agenda-source",
        source_type="agenda",
        payload_references={"raw_artifact_uri": "s3://pipeline/raw/meeting-pipeline-dlq-2.json"},
    )

    def _worker(_: StageWorkItem) -> None:
        raise TransientStageError("agenda endpoint timeout")

    first_result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)
    assert first_result.status == "failed"

    first_record = repository.list_pipeline_dlq_entries(run_id=run.id)[0]
    duplicate = repository.record_pipeline_dlq_entry(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id=item.meeting_id,
        stage_name="ingest",
        source_id=item.source_id,
        source_type="agenda",
        stage_outcome_id=first_record.stage_outcome_id,
        failure_classification="transient",
        terminal_reason="retry_exhausted",
        retry_policy_version=first_result.retry_policy_version,
        terminal_attempt_number=first_result.attempts,
        max_attempts=first_result.max_attempts,
        error_code="transient_stage_error",
        error_type="TransientStageError",
        error_message="agenda endpoint timeout",
        payload_references={"raw_artifact_uri": "s3://pipeline/raw/meeting-pipeline-dlq-2.json"},
        triage_metadata={"worker_name": "duplicate-terminal-insert"},
        terminal_transitioned_at="2026-03-07T11:00:30Z",
    )

    assert duplicate.id == first_record.id
    assert duplicate.terminal_transitioned_at == first_record.terminal_transitioned_at

    rerun_result = execution.execute_one(stage_name="ingest", item=item, worker=_worker)
    assert rerun_result.status == "failed"
    assert rerun_result.attempts == first_result.attempts

    all_records = repository.list_pipeline_dlq_entries(run_id=run.id)
    assert len(all_records) == 1
    assert all_records[0].id == first_record.id


def test_pipeline_dlq_records_are_queryable_by_stage_source_and_status(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )

    first_run = repository.create_pending_run(
        run_id="run-pipeline-dlq-query-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T12:00:00Z",
    )
    second_run = repository.create_pending_run(
        run_id="run-pipeline-dlq-query-2",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T12:05:00Z",
    )

    first_item = StageWorkItem(
        run_id=first_run.id,
        city_id=first_run.city_id,
        meeting_id="meeting-pipeline-dlq-query-1",
        source_id="query-source-agenda",
        source_type="agenda",
        payload_references={"raw_artifact_uri": "s3://pipeline/raw/meeting-pipeline-dlq-query-1.json"},
    )
    second_item = StageWorkItem(
        run_id=second_run.id,
        city_id=second_run.city_id,
        meeting_id="meeting-pipeline-dlq-query-2",
        source_id="query-source-bundle",
        source_type="bundle",
        payload_references={"extracted_text_uri": "s3://pipeline/extract/meeting-pipeline-dlq-query-2.txt"},
    )

    execution.execute_one(stage_name="ingest", item=first_item, worker=lambda _: (_ for _ in ()).throw(TransientStageError("agenda timeout")))
    execution.execute_one(stage_name="summarize", item=second_item, worker=lambda _: (_ for _ in ()).throw(TransientStageError("summary compose timeout")))

    ingest_records = repository.list_pipeline_dlq_entries(stage_name="ingest", source_id="query-source-agenda")
    summarize_records = repository.list_pipeline_dlq_entries(stage_name="summarize", status="open")

    assert [record.run_id for record in ingest_records] == [first_run.id]
    assert [record.run_id for record in summarize_records] == [second_run.id]
    assert all(record.status == "open" for record in summarize_records)
    assert PIPELINE_DLQ_STATUS_MODEL.can_transition(current="open", next_status="replay_ready")
    assert not PIPELINE_DLQ_STATUS_MODEL.can_transition(current="replayed", next_status="open")