from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from councilsense.app.pipeline_replay import (
    PipelineReplayCommandPayload,
    PipelineReplayCommandService,
    PipelineReplayExecutionService,
)
from councilsense.app.pipeline_retry import StageExecutionService, StageRetryPolicy, StageWorkItem, TransientStageError
from councilsense.app.summarization import SummarizationOutput, publish_summarization_output
from councilsense.db import (
    MeetingSummaryRepository,
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


def _create_pipeline_dlq_record(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    meeting_id: str,
    stage_name: str = "ingest",
    source_id: str = "pilot-minutes-source",
    source_type: str = "minutes",
) -> tuple[ProcessingRunRepository, object]:
    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    repository.create_pending_run(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        cycle_id=f"{run_id}-cycle",
    )
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )
    item = StageWorkItem(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        source_id=source_id,
        source_type=source_type,
        payload_references={"artifact_uri": f"s3://pipeline/{meeting_id}.json"},
    )

    def _worker(_: StageWorkItem) -> None:
        raise TransientStageError(f"{stage_name} worker failed")

    result = execution.execute_one(stage_name=stage_name, item=item, worker=_worker)
    assert result.final_disposition == "terminal"

    record = repository.list_pipeline_dlq_entries(run_id=run_id)[0]
    return repository, record


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, f"uid-{meeting_id}", "Council Meeting"),
    )


def _create_publish_replay_record(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    meeting_id: str,
    stage_status: str = "failed",
    materialize_publication: bool = False,
) -> tuple[ProcessingRunRepository, object]:
    repository = ProcessingRunRepository(connection)
    repository.create_pending_run(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        cycle_id=f"{run_id}-cycle",
    )
    _create_meeting(connection, meeting_id=meeting_id)
    outcome = repository.upsert_stage_outcome(
        outcome_id=f"outcome-publish-{run_id}-{meeting_id}",
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        stage_name="publish",
        status=stage_status,
        metadata_json='{"source_id":"bundle-source"}',
        started_at=None,
        finished_at=None,
    )
    dlq_record = repository.record_pipeline_dlq_entry(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        stage_name="publish",
        source_id="bundle-source",
        source_type="bundle",
        stage_outcome_id=outcome.id,
        failure_classification="terminal",
        terminal_reason="non_retryable",
        retry_policy_version="st029-stage-source-retry-policy.v1",
        terminal_attempt_number=1,
        max_attempts=3,
        error_code="terminal_stage_error",
        error_type="RuntimeError",
        error_message="publish failed",
        payload_references={"artifact_uri": f"s3://pipeline/{meeting_id}.json"},
        triage_metadata={"source_id": "bundle-source"},
    )

    if materialize_publication:
        publish_summarization_output(
            repository=MeetingSummaryRepository(connection),
            publication_id=f"pub-{meeting_id}-existing",
            meeting_id=meeting_id,
            processing_run_id=run_id,
            publish_stage_outcome_id=outcome.id,
            version_no=1,
            base_confidence_label="high",
            output=SummarizationOutput.from_sections(
                summary="Published summary",
                key_decisions=["Decision A"],
                key_actions=["Action A"],
                notable_topics=["Topic A"],
            ),
            published_at="2026-03-07T13:00:00Z",
            city_id=PILOT_CITY_ID,
        )

    refreshed = repository.get_pipeline_dlq_entry(dlq_key=dlq_record.dlq_key)
    assert refreshed is not None
    return repository, refreshed


def _submit_replay(repository: ProcessingRunRepository, *, dlq_key: str, idempotency_key: str):
    return PipelineReplayCommandService(repository=repository).submit(
        PipelineReplayCommandPayload.model_validate(
            {
                "dlq_key": dlq_key,
                "actor_user_id": "operator-replay",
                "reason": "manual replay",
                "idempotency_key": idempotency_key,
            }
        )
    )


@pytest.mark.parametrize(
    ("payload", "field_name"),
    (
        ({"dlq_key": "pipeline-dlq:1", "reason": "manual retry", "idempotency_key": "idem-1"}, "actor_user_id"),
        ({"dlq_key": "pipeline-dlq:1", "actor_user_id": "operator-1", "idempotency_key": "idem-1"}, "reason"),
        ({"dlq_key": "pipeline-dlq:1", "actor_user_id": "operator-1", "reason": "manual retry"}, "idempotency_key"),
        (
            {
                "dlq_key": "pipeline-dlq:1",
                "actor_user_id": "   ",
                "reason": "manual retry",
                "idempotency_key": "idem-1",
            },
            "actor_user_id",
        ),
        (
            {
                "dlq_key": "pipeline-dlq:1",
                "actor_user_id": "operator-1",
                "reason": "   ",
                "idempotency_key": "idem-1",
            },
            "reason",
        ),
    ),
)
def test_pipeline_replay_command_payload_rejects_missing_or_blank_metadata(
    payload: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        PipelineReplayCommandPayload.model_validate(payload)

    assert field_name in str(excinfo.value)


def test_pipeline_replay_command_records_requested_and_queued_audit_history(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_pipeline_dlq_record(
        connection,
        run_id="run-pipeline-replay-success",
        meeting_id="meeting-pipeline-replay-success",
    )
    service = PipelineReplayCommandService(repository=repository)

    payload = PipelineReplayCommandPayload.model_validate(
        {
            "dlq_key": dlq_record.dlq_key,
            "actor_user_id": "operator-1",
            "reason": "upstream source fixed",
            "idempotency_key": "idem-success-1",
        }
    )
    result = service.submit(payload)
    second_result = service.submit(payload)

    assert result.outcome == "queued"
    assert result.status_before == "open"
    assert result.status_after == "replay_ready"
    assert second_result == result

    refreshed = repository.get_pipeline_dlq_entry(dlq_key=dlq_record.dlq_key)
    assert refreshed is not None
    assert refreshed.status == "replay_ready"
    assert refreshed.replay_ready_at is not None

    history = repository.list_pipeline_replay_audit_records(
        run_id=dlq_record.run_id,
        stage_name=dlq_record.stage_name,
        actor_user_id="operator-1",
    )
    assert [event.event_type for event in history] == ["requested", "queued"]
    assert all(event.dlq_entry_id == dlq_record.id for event in history)
    assert all(event.meeting_id == dlq_record.meeting_id for event in history)
    assert all(event.source_id == dlq_record.source_id for event in history)

    result_metadata = json.loads(history[1].result_metadata_json)
    assert result_metadata == {
        "city_id": PILOT_CITY_ID,
        "dlq_entry_id": dlq_record.id,
        "dlq_key": dlq_record.dlq_key,
        "meeting_id": dlq_record.meeting_id,
        "reason_code": None,
        "run_id": dlq_record.run_id,
        "source_id": dlq_record.source_id,
        "stage_name": dlq_record.stage_name,
        "stage_outcome_id": dlq_record.stage_outcome_id,
        "status_after": "replay_ready",
        "status_before": "open",
        "transition_applied": True,
    }


@pytest.mark.parametrize(
    ("starting_status", "expected_outcome", "expected_reason_code"),
    (
        ("replay_ready", "noop", "already_replay_ready"),
        ("replayed", "noop", "already_replayed"),
        ("dismissed", "failed", "dismissed_dlq_not_replayable"),
    ),
)
def test_pipeline_replay_command_records_noop_and_failed_audit_outcomes(
    connection: sqlite3.Connection,
    starting_status: str,
    expected_outcome: str,
    expected_reason_code: str,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_pipeline_dlq_record(
        connection,
        run_id=f"run-pipeline-replay-{starting_status}",
        meeting_id=f"meeting-pipeline-replay-{starting_status}",
    )

    if starting_status != "open":
        repository.transition_pipeline_dlq_status(dlq_key=dlq_record.dlq_key, next_status="replay_ready")
        if starting_status == "replayed":
            repository.transition_pipeline_dlq_status(dlq_key=dlq_record.dlq_key, next_status="replayed")
        elif starting_status == "dismissed":
            record = repository.get_pipeline_dlq_entry(dlq_key=dlq_record.dlq_key)
            assert record is not None
            connection.execute(
                """
                UPDATE pipeline_dlq_entries
                SET status = 'dismissed', updated_at = CURRENT_TIMESTAMP
                WHERE dlq_key = ?
                """,
                (dlq_record.dlq_key,),
            )

    service = PipelineReplayCommandService(repository=repository)
    result = service.submit(
        PipelineReplayCommandPayload.model_validate(
            {
                "dlq_key": dlq_record.dlq_key,
                "actor_user_id": "operator-2",
                "reason": "manual replay review",
                "idempotency_key": f"idem-{starting_status}",
            }
        )
    )

    assert result.outcome == expected_outcome
    history = repository.list_pipeline_replay_audit_records(dlq_key=dlq_record.dlq_key, actor_user_id="operator-2")
    assert [event.event_type for event in history] == ["requested", expected_outcome]

    result_metadata = json.loads(history[1].result_metadata_json)
    assert result_metadata["reason_code"] == expected_reason_code
    assert result_metadata["status_before"] == starting_status
    assert result_metadata["status_after"] == starting_status
    assert result_metadata["transition_applied"] is False


def test_pipeline_replay_execution_short_circuits_already_processed_stage_before_worker(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_pipeline_dlq_record(
        connection,
        run_id="run-pipeline-replay-exec-processed",
        meeting_id="meeting-pipeline-replay-exec-processed",
    )
    repository.upsert_stage_outcome(
        outcome_id=dlq_record.stage_outcome_id,
        run_id=dlq_record.run_id,
        city_id=dlq_record.city_id,
        meeting_id=dlq_record.meeting_id,
        stage_name=dlq_record.stage_name,
        status="processed",
        metadata_json='{"source_id":"pilot-minutes-source"}',
        started_at=None,
        finished_at=None,
    )
    submitted = _submit_replay(repository, dlq_key=dlq_record.dlq_key, idempotency_key="idem-exec-processed")
    service = PipelineReplayExecutionService(repository=repository)

    result = service.execute(
        replay_request_key=submitted.replay_request_key,
        worker=lambda: (_ for _ in ()).throw(AssertionError("worker should not run")),
    )

    assert result.outcome == "noop"
    assert result.guard_reason_code == "stage_already_processed"

    history = repository.list_pipeline_replay_audit_records(replay_request_key=submitted.replay_request_key)
    assert [event.event_type for event in history] == ["requested", "queued", "noop"]

    noop_metadata = json.loads(history[-1].result_metadata_json)
    assert noop_metadata["guard_applied"] is True
    assert noop_metadata["guard_reason_code"] == "stage_already_processed"


def test_pipeline_replay_execution_short_circuits_publish_when_publication_already_exists(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_publish_replay_record(
        connection,
        run_id="run-pipeline-replay-exec-partial",
        meeting_id="meeting-pipeline-replay-exec-partial",
        materialize_publication=True,
    )
    submitted = _submit_replay(repository, dlq_key=dlq_record.dlq_key, idempotency_key="idem-exec-partial")
    service = PipelineReplayExecutionService(repository=repository)

    result = service.execute(
        replay_request_key=submitted.replay_request_key,
        worker=lambda: (_ for _ in ()).throw(AssertionError("worker should not run")),
    )

    assert result.outcome == "noop"
    assert result.guard_reason_code == "publish_stage_outcome_already_materialized"

    history = repository.list_pipeline_replay_audit_records(replay_request_key=submitted.replay_request_key)
    noop_metadata = json.loads(history[-1].result_metadata_json)
    assert noop_metadata["publication_id"] == "pub-meeting-pipeline-replay-exec-partial-existing"
    assert noop_metadata["guard_reason_code"] == "publish_stage_outcome_already_materialized"

    publication_count = connection.execute(
        "SELECT COUNT(*) FROM summary_publications WHERE publish_stage_outcome_id = ?",
        (dlq_record.stage_outcome_id,),
    ).fetchone()
    assert publication_count is not None
    assert int(publication_count[0]) == 1


def test_pipeline_replay_execution_records_failed_attempts_in_audit_history(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_pipeline_dlq_record(
        connection,
        run_id="run-pipeline-replay-exec-failed",
        meeting_id="meeting-pipeline-replay-exec-failed",
    )
    submitted = _submit_replay(repository, dlq_key=dlq_record.dlq_key, idempotency_key="idem-exec-failed")
    service = PipelineReplayExecutionService(repository=repository)

    result = service.execute(
        replay_request_key=submitted.replay_request_key,
        worker=lambda: (_ for _ in ()).throw(RuntimeError("replay failed again")),
    )

    assert result.outcome == "failed"
    assert result.guard_reason_code is None

    history = repository.list_pipeline_replay_audit_records(replay_request_key=submitted.replay_request_key)
    assert [event.event_type for event in history] == ["requested", "queued", "failed"]

    failed_metadata = json.loads(history[-1].result_metadata_json)
    assert failed_metadata["reason_code"] == "replay_worker_failed"
    assert failed_metadata["error_type"] == "RuntimeError"
    assert failed_metadata["error_message"] == "replay failed again"


def test_pipeline_replay_execution_is_idempotent_on_repeated_attempts_after_success(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_pipeline_dlq_record(
        connection,
        run_id="run-pipeline-replay-exec-repeat",
        meeting_id="meeting-pipeline-replay-exec-repeat",
    )
    submitted = _submit_replay(repository, dlq_key=dlq_record.dlq_key, idempotency_key="idem-exec-repeat")
    service = PipelineReplayExecutionService(repository=repository)
    worker_calls = {"count": 0}

    def _worker() -> None:
        worker_calls["count"] += 1
        repository.upsert_stage_outcome(
            outcome_id=dlq_record.stage_outcome_id,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            status="processed",
            metadata_json='{"source_id":"pilot-minutes-source"}',
            started_at=None,
            finished_at=None,
        )

    first = service.execute(replay_request_key=submitted.replay_request_key, worker=_worker)
    second = service.execute(replay_request_key=submitted.replay_request_key, worker=_worker)

    assert first.outcome == "replayed"
    assert second.outcome == "replayed"
    assert second.guard_reason_code == "dlq_already_replayed"
    assert worker_calls["count"] == 1