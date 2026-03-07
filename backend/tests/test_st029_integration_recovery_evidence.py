from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator

import pytest

from councilsense.app.pipeline_replay import PipelineReplayCommandPayload, PipelineReplayCommandService, PipelineReplayExecutionService
from councilsense.app.pipeline_retry import StageExecutionService, StageRetryPolicy, StageWorkItem, TransientStageError
from councilsense.app.summarization import SummarizationOutput, publish_summarization_output
from councilsense.db import MeetingSummaryRepository, PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _pipeline_events(caplog: pytest.LogCaptureFixture) -> tuple[dict[str, object], ...]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        event = getattr(record, "event", None)
        if isinstance(event, dict) and str(event.get("event_name", "")).startswith("pipeline_"):
            events.append(event)
    return tuple(events)


def _submit_replay(repository: ProcessingRunRepository, *, dlq_key: str, actor_user_id: str, reason: str, idempotency_key: str):
    return PipelineReplayCommandService(repository=repository).submit(
        PipelineReplayCommandPayload.model_validate(
            {
                "dlq_key": dlq_key,
                "actor_user_id": actor_user_id,
                "reason": reason,
                "idempotency_key": idempotency_key,
            }
        )
    )


def _create_publish_replay_record(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    meeting_id: str,
) -> tuple[ProcessingRunRepository, object]:
    repository = ProcessingRunRepository(connection)
    repository.create_pending_run(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        cycle_id=f"{run_id}-cycle",
    )
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, f"uid-{meeting_id}", "Council Meeting"),
    )
    outcome = repository.upsert_stage_outcome(
        outcome_id=f"outcome-publish-{run_id}-{meeting_id}",
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        stage_name="publish",
        status="failed",
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


def test_st029_retry_cap_dlq_replay_success_flow_has_release_evidence(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    repository.create_pending_run(
        run_id="run-st029-release-evidence",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T15:00:00Z",
    )
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=2),
    )
    item = StageWorkItem(
        run_id="run-st029-release-evidence",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-st029-release-evidence",
        source_id="pilot-minutes-source",
        source_type="minutes",
        payload_references={"raw_artifact_uri": "s3://pipeline/raw/meeting-st029-release-evidence.json"},
    )

    caplog.set_level(logging.INFO)

    result = execution.execute_one(
        stage_name="ingest",
        item=item,
        worker=lambda _: (_ for _ in ()).throw(TransientStageError("upstream minutes fetch timed out")),
    )

    assert result.status == "failed"
    assert result.attempts == 2
    assert result.final_disposition == "terminal"

    dlq_record = repository.list_pipeline_dlq_entries(run_id=item.run_id)[0]
    assert dlq_record.status == "open"
    assert dlq_record.terminal_reason == "retry_exhausted"
    assert dlq_record.terminal_attempt_number == 2

    submitted = _submit_replay(
        repository,
        dlq_key=dlq_record.dlq_key,
        actor_user_id="operator-recovery",
        reason="source endpoint recovered",
        idempotency_key="idem-st029-release-evidence",
    )
    replay_service = PipelineReplayExecutionService(repository=repository)

    replay_result = replay_service.execute(
        replay_request_key=submitted.replay_request_key,
        worker=lambda: repository.upsert_stage_outcome(
            outcome_id=dlq_record.stage_outcome_id,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            status="processed",
            metadata_json='{"source_id":"pilot-minutes-source"}',
            started_at=None,
            finished_at=None,
        ),
    )

    assert replay_result.outcome == "replayed"
    assert replay_result.dlq_status_before == "replay_ready"
    assert replay_result.dlq_status_after == "replayed"
    assert replay_result.stage_status_after == "processed"

    history = repository.list_pipeline_replay_audit_records(replay_request_key=submitted.replay_request_key)
    assert [event.event_type for event in history] == ["requested", "queued", "replayed"]
    assert all(event.actor_user_id == "operator-recovery" for event in history)
    assert all(event.replay_reason == "source endpoint recovered" for event in history)
    assert all(event.idempotency_key == "idem-st029-release-evidence" for event in history)

    replayed_metadata = json.loads(history[-1].result_metadata_json)
    assert replayed_metadata["guard_applied"] is False
    assert replayed_metadata["guard_reason_code"] is None
    assert replayed_metadata["dlq_status_before"] == "replay_ready"
    assert replayed_metadata["dlq_status_after"] == "replayed"
    assert replayed_metadata["stage_status_before"] == "failed"
    assert replayed_metadata["stage_status_after"] == "processed"

    events = _pipeline_events(caplog)
    stage_errors = [
        event for event in events if event.get("event_name") == "pipeline_stage_error" and event.get("meeting_id") == item.meeting_id
    ]
    assert [event["outcome"] for event in stage_errors] == ["retry", "failure"]
    assert stage_errors[-1]["failure_classification"] == "transient"
    assert stage_errors[-1]["error_code"] == "transient_stage_error"
    assert stage_errors[-1]["retry_policy_version"] == result.retry_policy_version

    replay_events = [event for event in events if event.get("dedupe_key") == submitted.replay_request_key]
    assert [event["event_name"] for event in replay_events] == ["pipeline_replay_command", "pipeline_replay_execution"]
    assert replay_events[0]["replay_outcome"] == "queued"
    assert replay_events[0]["actor_user_id"] == "operator-recovery"
    assert replay_events[0]["idempotency_key"] == "idem-st029-release-evidence"
    assert replay_events[1]["replay_outcome"] == "replayed"
    assert replay_events[1]["outcome"] == "success"
    assert replay_events[1]["guard_reason_code"] is None


def test_st029_publish_replay_noop_stays_single_publication_and_records_guarded_outcome(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    repository, dlq_record = _create_publish_replay_record(
        connection,
        run_id="run-st029-publish-noop",
        meeting_id="meeting-st029-publish-noop",
    )

    caplog.set_level(logging.INFO)

    submitted = _submit_replay(
        repository,
        dlq_key=dlq_record.dlq_key,
        actor_user_id="operator-noop",
        reason="verify duplicate-safe recovery",
        idempotency_key="idem-st029-publish-noop",
    )

    result = PipelineReplayExecutionService(repository=repository).execute(
        replay_request_key=submitted.replay_request_key,
        worker=lambda: (_ for _ in ()).throw(AssertionError("worker should not run")),
    )

    assert result.outcome == "noop"
    assert result.guard_reason_code == "publish_stage_outcome_already_materialized"

    history = repository.list_pipeline_replay_audit_records(replay_request_key=submitted.replay_request_key)
    assert [event.event_type for event in history] == ["requested", "queued", "noop"]

    noop_metadata = json.loads(history[-1].result_metadata_json)
    assert noop_metadata["guard_applied"] is True
    assert noop_metadata["guard_reason_code"] == "publish_stage_outcome_already_materialized"
    assert noop_metadata["publication_id"] == "pub-meeting-st029-publish-noop-existing"
    assert noop_metadata["dlq_status_before"] == "replay_ready"
    assert noop_metadata["dlq_status_after"] == "replayed"

    publication_count = connection.execute(
        "SELECT COUNT(*) FROM summary_publications WHERE publish_stage_outcome_id = ?",
        (dlq_record.stage_outcome_id,),
    ).fetchone()
    assert publication_count is not None
    assert int(publication_count[0]) == 1

    replay_events = [event for event in _pipeline_events(caplog) if event.get("dedupe_key") == submitted.replay_request_key]
    assert [event["event_name"] for event in replay_events] == ["pipeline_replay_command", "pipeline_replay_execution"]
    assert replay_events[-1]["replay_outcome"] == "noop"
    assert replay_events[-1]["outcome"] == "suppressed"
    assert replay_events[-1]["guard_reason_code"] == "publish_stage_outcome_already_materialized"