from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from councilsense.app.pipeline_replay import PipelineReplayCommandPayload, PipelineReplayCommandService
from councilsense.app.pipeline_retry import StageExecutionService, StageRetryPolicy, StageWorkItem, TransientStageError
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


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