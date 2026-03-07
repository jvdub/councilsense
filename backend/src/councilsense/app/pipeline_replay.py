from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from councilsense.db import MeetingSummaryRepository, ProcessingRunRepository, build_pipeline_replay_request_key


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


@dataclass(frozen=True)
class PipelineReplayExecutionResult:
    replay_request_key: str
    dlq_key: str
    run_id: str
    city_id: str
    meeting_id: str
    stage_name: str
    source_id: str
    outcome: str
    dlq_status_before: str
    dlq_status_after: str
    stage_status_before: str | None
    stage_status_after: str | None
    guard_reason_code: str | None
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


class PipelineReplayExecutionService:
    def __init__(self, *, repository: ProcessingRunRepository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        replay_request_key: str,
        worker: Callable[[], object],
    ) -> PipelineReplayExecutionResult:
        history = self._repository.list_pipeline_replay_audit_records(
            replay_request_key=replay_request_key,
            limit=10,
        )
        if not history:
            raise PipelineReplayNotFoundError(replay_request_key)

        persisted_result = self._existing_execution_result(history)
        if persisted_result is not None:
            return persisted_result

        requested = None
        for event in history:
            if event.event_type == "requested":
                requested = event
                break
        if requested is None:
            raise RuntimeError("Replay audit history is missing the requested event")

        dlq_record = self._repository.get_pipeline_dlq_entry(dlq_key=requested.dlq_key)
        if dlq_record is None:
            raise PipelineReplayNotFoundError(requested.dlq_key)

        stage_outcome = self._repository.get_stage_outcome(
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
        )
        dlq_status_before = dlq_record.status
        stage_status_before = getattr(stage_outcome, "status", None)

        if dlq_record.status == "replayed":
            result_metadata = {
                "dlq_status_before": dlq_status_before,
                "dlq_status_after": dlq_record.status,
                "stage_status_before": stage_status_before,
                "stage_status_after": stage_status_before,
                "guard_applied": True,
                "guard_reason_code": "dlq_already_replayed",
            }
            return PipelineReplayExecutionResult(
                replay_request_key=replay_request_key,
                dlq_key=dlq_record.dlq_key,
                run_id=dlq_record.run_id,
                city_id=dlq_record.city_id,
                meeting_id=dlq_record.meeting_id,
                stage_name=dlq_record.stage_name,
                source_id=dlq_record.source_id,
                outcome="replayed",
                dlq_status_before=dlq_status_before,
                dlq_status_after=dlq_record.status,
                stage_status_before=stage_status_before,
                stage_status_after=stage_status_before,
                guard_reason_code="dlq_already_replayed",
                completed_at=dlq_record.replayed_at or requested.created_at,
                result_metadata_json=json.dumps(result_metadata, sort_keys=True, separators=(",", ":")),
            )

        guard_result = self._guard_replay(
            dlq_record=dlq_record,
            stage_status_before=stage_status_before,
        )
        if guard_result is not None:
            return self._record_execution_event(
                requested=requested,
                dlq_status_before=dlq_status_before,
                stage_status_before=stage_status_before,
                stage_status_after=stage_status_before,
                event_type="noop",
                result_metadata=guard_result,
                transition_to_replayed=True,
            )

        try:
            worker()
        except Exception as exc:
            return self._record_execution_event(
                requested=requested,
                dlq_status_before=dlq_status_before,
                stage_status_before=stage_status_before,
                stage_status_after=self._current_stage_status(requested=requested),
                event_type="failed",
                result_metadata={
                    "guard_applied": False,
                    "guard_reason_code": None,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "reason_code": "replay_worker_failed",
                },
                transition_to_replayed=False,
            )

        if dlq_record.status == "replay_ready":
            transitioned = self._repository.transition_pipeline_dlq_status(
                dlq_key=dlq_record.dlq_key,
                next_status="replayed",
            )
            dlq_status_after = transitioned.status
        else:
            dlq_status_after = dlq_record.status

        return PipelineReplayExecutionResult(
            replay_request_key=replay_request_key,
            dlq_key=dlq_record.dlq_key,
            run_id=dlq_record.run_id,
            city_id=dlq_record.city_id,
            meeting_id=dlq_record.meeting_id,
            stage_name=dlq_record.stage_name,
            source_id=dlq_record.source_id,
            outcome="replayed",
            dlq_status_before=dlq_status_before,
            dlq_status_after=dlq_status_after,
            stage_status_before=stage_status_before,
            stage_status_after=self._current_stage_status(requested=requested),
            guard_reason_code=None,
            completed_at=transitioned.replayed_at if dlq_record.status == "replay_ready" and dlq_status_after == "replayed" else requested.created_at,
            result_metadata_json=json.dumps(
                {
                    "dlq_status_before": dlq_status_before,
                    "dlq_status_after": dlq_status_after,
                    "stage_status_before": stage_status_before,
                    "stage_status_after": self._current_stage_status(requested=requested),
                    "guard_applied": False,
                    "guard_reason_code": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def _guard_replay(
        self,
        *,
        dlq_record: object,
        stage_status_before: str | None,
    ) -> dict[str, object] | None:
        if stage_status_before == "processed":
            return {
                "guard_applied": True,
                "guard_reason_code": "stage_already_processed",
                "reason_code": "stage_already_processed",
            }

        if getattr(dlq_record, "stage_name", None) == "publish":
            publication = MeetingSummaryRepository(self._repository._connection).get_publication_by_publish_stage_outcome_id(
                publish_stage_outcome_id=str(getattr(dlq_record, "stage_outcome_id")),
            )
            if publication is not None:
                return {
                    "guard_applied": True,
                    "guard_reason_code": "publish_stage_outcome_already_materialized",
                    "reason_code": "publish_stage_outcome_already_materialized",
                    "publication_id": publication.id,
                    "publication_status": publication.publication_status,
                    "publication_version_no": publication.version_no,
                }

        return None

    def _record_execution_event(
        self,
        *,
        requested: object,
        dlq_status_before: str,
        stage_status_before: str | None,
        stage_status_after: str | None,
        event_type: str,
        result_metadata: dict[str, object],
        transition_to_replayed: bool,
    ) -> PipelineReplayExecutionResult:
        dlq_status_after = dlq_status_before
        if transition_to_replayed and requested.dlq_key is not None:
            dlq_record = self._repository.get_pipeline_dlq_entry(dlq_key=requested.dlq_key)
            if dlq_record is not None and dlq_record.status == "replay_ready":
                dlq_status_after = self._repository.transition_pipeline_dlq_status(
                    dlq_key=requested.dlq_key,
                    next_status="replayed",
                ).status

        completed = self._repository.record_pipeline_replay_audit_event(
            replay_request_key=requested.replay_request_key,
            idempotency_key=requested.idempotency_key,
            dlq_entry_id=requested.dlq_entry_id,
            dlq_key=requested.dlq_key,
            run_id=requested.run_id,
            city_id=requested.city_id,
            meeting_id=requested.meeting_id,
            stage_name=requested.stage_name,
            source_id=requested.source_id,
            stage_outcome_id=requested.stage_outcome_id,
            actor_user_id=requested.actor_user_id,
            replay_reason=requested.replay_reason,
            event_type=event_type,
            result_metadata={
                **result_metadata,
                "dlq_status_before": dlq_status_before,
                "dlq_status_after": dlq_status_after,
                "stage_status_before": stage_status_before,
                "stage_status_after": stage_status_after,
            },
        )
        metadata = json.loads(completed.result_metadata_json)
        return PipelineReplayExecutionResult(
            replay_request_key=completed.replay_request_key,
            dlq_key=completed.dlq_key,
            run_id=completed.run_id,
            city_id=completed.city_id,
            meeting_id=completed.meeting_id,
            stage_name=completed.stage_name,
            source_id=completed.source_id,
            outcome=completed.event_type,
            dlq_status_before=str(metadata["dlq_status_before"]),
            dlq_status_after=str(metadata["dlq_status_after"]),
            stage_status_before=(str(metadata["stage_status_before"]) if metadata["stage_status_before"] is not None else None),
            stage_status_after=(str(metadata["stage_status_after"]) if metadata["stage_status_after"] is not None else None),
            guard_reason_code=(str(metadata["guard_reason_code"]) if metadata.get("guard_reason_code") is not None else None),
            completed_at=completed.created_at,
            result_metadata_json=completed.result_metadata_json,
        )

    def _current_stage_status(self, *, requested: object) -> str | None:
        stage_outcome = self._repository.get_stage_outcome(
            run_id=requested.run_id,
            city_id=requested.city_id,
            meeting_id=requested.meeting_id,
            stage_name=requested.stage_name,
        )
        return getattr(stage_outcome, "status", None)

    @staticmethod
    def _existing_execution_result(history: tuple[object, ...]) -> PipelineReplayExecutionResult | None:
        for event in history:
            if getattr(event, "event_type", None) not in {"noop", "failed"}:
                continue
            metadata = json.loads(event.result_metadata_json)
            if "dlq_status_before" not in metadata or "dlq_status_after" not in metadata:
                continue
            return PipelineReplayExecutionResult(
                replay_request_key=event.replay_request_key,
                dlq_key=event.dlq_key,
                run_id=event.run_id,
                city_id=event.city_id,
                meeting_id=event.meeting_id,
                stage_name=event.stage_name,
                source_id=event.source_id,
                outcome=event.event_type,
                dlq_status_before=str(metadata["dlq_status_before"]),
                dlq_status_after=str(metadata["dlq_status_after"]),
                stage_status_before=(str(metadata["stage_status_before"]) if metadata["stage_status_before"] is not None else None),
                stage_status_after=(str(metadata["stage_status_after"]) if metadata["stage_status_after"] is not None else None),
                guard_reason_code=(str(metadata["guard_reason_code"]) if metadata.get("guard_reason_code") is not None else None),
                completed_at=event.created_at,
                result_metadata_json=event.result_metadata_json,
            )
        return None