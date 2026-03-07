from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from councilsense.db import ProcessingRunRepository, build_pipeline_replay_request_key


class PipelineReplayNotFoundError(LookupError):
    pass


class PipelineReplayCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dlq_key: str = Field(min_length=1)
    actor_user_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)

    @field_validator("dlq_key", "actor_user_id", "reason", "idempotency_key")
    @classmethod
    def _normalize_non_empty_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


@dataclass(frozen=True)
class PipelineReplayCommandResult:
    replay_request_key: str
    idempotency_key: str
    dlq_key: str
    dlq_entry_id: int
    run_id: str
    city_id: str
    meeting_id: str
    stage_name: str
    source_id: str
    actor_user_id: str
    replay_reason: str
    outcome: str
    status_before: str
    status_after: str
    requested_at: str
    completed_at: str
    result_metadata_json: str


class PipelineReplayCommandService:
    def __init__(self, *, repository: ProcessingRunRepository) -> None:
        self._repository = repository

    def submit(self, payload: PipelineReplayCommandPayload) -> PipelineReplayCommandResult:
        replay_request_key = build_pipeline_replay_request_key(
            dlq_key=payload.dlq_key,
            idempotency_key=payload.idempotency_key,
        )
        existing_history = self._repository.list_pipeline_replay_audit_records(
            replay_request_key=replay_request_key,
            limit=10,
        )
        if existing_history:
            return self._to_result(existing_history)

        dlq_record = self._repository.get_pipeline_dlq_entry(dlq_key=payload.dlq_key)
        if dlq_record is None:
            raise PipelineReplayNotFoundError(payload.dlq_key)

        requested = self._repository.record_pipeline_replay_audit_event(
            replay_request_key=replay_request_key,
            idempotency_key=payload.idempotency_key,
            dlq_entry_id=dlq_record.id,
            dlq_key=dlq_record.dlq_key,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            source_id=dlq_record.source_id,
            stage_outcome_id=dlq_record.stage_outcome_id,
            actor_user_id=payload.actor_user_id,
            replay_reason=payload.reason,
            event_type="requested",
            result_metadata={
                "status_before": dlq_record.status,
                "status_after": dlq_record.status,
                "transition_applied": False,
            },
        )

        outcome = "queued"
        status_after = dlq_record.status
        transition_applied = False
        reason_code: str | None = None

        if dlq_record.status in {"open", "triaged"}:
            transitioned = self._repository.transition_pipeline_dlq_status(
                dlq_key=dlq_record.dlq_key,
                next_status="replay_ready",
            )
            status_after = transitioned.status
            transition_applied = True
        elif dlq_record.status == "replay_ready":
            outcome = "noop"
            reason_code = "already_replay_ready"
        elif dlq_record.status == "replayed":
            outcome = "noop"
            reason_code = "already_replayed"
        else:
            outcome = "failed"
            reason_code = "dismissed_dlq_not_replayable"

        completed = self._repository.record_pipeline_replay_audit_event(
            replay_request_key=replay_request_key,
            idempotency_key=payload.idempotency_key,
            dlq_entry_id=dlq_record.id,
            dlq_key=dlq_record.dlq_key,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            source_id=dlq_record.source_id,
            stage_outcome_id=dlq_record.stage_outcome_id,
            actor_user_id=payload.actor_user_id,
            replay_reason=payload.reason,
            event_type=outcome,
            result_metadata={
                "status_before": dlq_record.status,
                "status_after": status_after,
                "transition_applied": transition_applied,
                "reason_code": reason_code,
                "dlq_entry_id": dlq_record.id,
                "dlq_key": dlq_record.dlq_key,
                "run_id": dlq_record.run_id,
                "city_id": dlq_record.city_id,
                "meeting_id": dlq_record.meeting_id,
                "stage_name": dlq_record.stage_name,
                "source_id": dlq_record.source_id,
                "stage_outcome_id": dlq_record.stage_outcome_id,
            },
        )

        return PipelineReplayCommandResult(
            replay_request_key=replay_request_key,
            idempotency_key=payload.idempotency_key,
            dlq_key=dlq_record.dlq_key,
            dlq_entry_id=dlq_record.id,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            source_id=dlq_record.source_id,
            actor_user_id=payload.actor_user_id,
            replay_reason=payload.reason,
            outcome=completed.event_type,
            status_before=dlq_record.status,
            status_after=status_after,
            requested_at=requested.created_at,
            completed_at=completed.created_at,
            result_metadata_json=completed.result_metadata_json,
        )

    @staticmethod
    def _to_result(history: tuple[object, ...]) -> PipelineReplayCommandResult:
        requested = None
        completed = None
        for event in history:
            if getattr(event, "event_type", None) == "requested":
                requested = event
            elif getattr(event, "event_type", None) in {"queued", "noop", "failed"}:
                completed = event
        if requested is None or completed is None:
            raise RuntimeError("Replay audit history is incomplete for idempotent request")

        result_metadata = json.loads(completed.result_metadata_json)
        return PipelineReplayCommandResult(
            replay_request_key=completed.replay_request_key,
            idempotency_key=completed.idempotency_key,
            dlq_key=completed.dlq_key,
            dlq_entry_id=completed.dlq_entry_id,
            run_id=completed.run_id,
            city_id=completed.city_id,
            meeting_id=completed.meeting_id,
            stage_name=completed.stage_name,
            source_id=completed.source_id,
            actor_user_id=completed.actor_user_id,
            replay_reason=completed.replay_reason,
            outcome=completed.event_type,
            status_before=str(result_metadata["status_before"]),
            status_after=str(result_metadata["status_after"]),
            requested_at=requested.created_at,
            completed_at=completed.created_at,
            result_metadata_json=completed.result_metadata_json,
        )