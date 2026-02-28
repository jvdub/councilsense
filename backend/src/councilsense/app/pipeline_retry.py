from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable, Literal

from councilsense.db import (
    ProcessingLifecycleService,
    ProcessingRunRepository,
    RunLifecycleStatus,
    SourceHealthRepository,
)


FailureClassification = Literal["transient", "permanent"]


logger = logging.getLogger(__name__)


class TransientStageError(RuntimeError):
    pass


class PermanentStageError(RuntimeError):
    pass


def classify_stage_error(error: Exception) -> FailureClassification:
    if isinstance(error, TransientStageError):
        return "transient"
    return "permanent"


@dataclass(frozen=True)
class StageRetryPolicy:
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")


@dataclass(frozen=True)
class StageWorkItem:
    run_id: str
    city_id: str
    meeting_id: str
    source_id: str


@dataclass(frozen=True)
class StageExecutionResult:
    run_id: str
    city_id: str
    meeting_id: str
    source_id: str
    status: RunLifecycleStatus
    attempts: int
    failure_classification: FailureClassification | None


class StageExecutionService:
    def __init__(
        self,
        *,
        repository: ProcessingRunRepository,
        lifecycle_service: ProcessingLifecycleService,
        source_health_repository: SourceHealthRepository | None = None,
        retry_policy: StageRetryPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._lifecycle_service = lifecycle_service
        self._source_health_repository = source_health_repository
        self._retry_policy = retry_policy or StageRetryPolicy()

    def execute_many(
        self,
        *,
        stage_name: str,
        items: tuple[StageWorkItem, ...],
        worker: Callable[[StageWorkItem], None],
    ) -> tuple[StageExecutionResult, ...]:
        return tuple(self.execute_one(stage_name=stage_name, item=item, worker=worker) for item in items)

    def execute_one(
        self,
        *,
        stage_name: str,
        item: StageWorkItem,
        worker: Callable[[StageWorkItem], None],
    ) -> StageExecutionResult:
        attempts = 0
        while attempts < self._retry_policy.max_attempts:
            attempts += 1
            self._log_stage_event(
                event_name="pipeline_stage_started",
                stage_name=stage_name,
                outcome="retry" if attempts > 1 else "success",
                item=item,
                attempt=attempts,
                error_code=None,
                error_message=None,
            )
            try:
                worker(item)
                self._record_ingest_attempt(
                    stage_name=stage_name,
                    source_id=item.source_id,
                    succeeded=True,
                    failure_reason=None,
                )
                self._repository.upsert_stage_outcome(
                    outcome_id=_outcome_id(stage_name=stage_name, item=item),
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    stage_name=stage_name,
                    status="processed",
                    metadata_json=_metadata_json(
                        attempts=attempts,
                        source_id=item.source_id,
                        failure_classification=None,
                        error_type=None,
                        error_message=None,
                    ),
                    started_at=None,
                    finished_at=None,
                )
                self._log_stage_event(
                    event_name="pipeline_stage_finished",
                    stage_name=stage_name,
                    outcome="success",
                    item=item,
                    attempt=attempts,
                    error_code=None,
                    error_message=None,
                )
                self._lifecycle_service.mark_processed(run_id=item.run_id)
                return StageExecutionResult(
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    source_id=item.source_id,
                    status="processed",
                    attempts=attempts,
                    failure_classification=None,
                )
            except Exception as error:
                failure_classification = classify_stage_error(error)
                if failure_classification == "transient" and attempts < self._retry_policy.max_attempts:
                    self._log_stage_event(
                        event_name="pipeline_stage_error",
                        stage_name=stage_name,
                        outcome="retry",
                        item=item,
                        attempt=attempts,
                        error_code=_error_code_for_exception(error),
                        error_message=_short_error_message(error),
                    )
                    continue

                self._record_ingest_attempt(
                    stage_name=stage_name,
                    source_id=item.source_id,
                    succeeded=False,
                    failure_reason=f"{type(error).__name__}: {error}",
                )

                self._repository.upsert_stage_outcome(
                    outcome_id=_outcome_id(stage_name=stage_name, item=item),
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    stage_name=stage_name,
                    status="failed",
                    metadata_json=_metadata_json(
                        attempts=attempts,
                        source_id=item.source_id,
                        failure_classification=failure_classification,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    ),
                    started_at=None,
                    finished_at=None,
                )
                self._log_stage_event(
                    event_name="pipeline_stage_error",
                    stage_name=stage_name,
                    outcome="failure",
                    item=item,
                    attempt=attempts,
                    error_code=_error_code_for_exception(error),
                    error_message=_short_error_message(error),
                )
                self._lifecycle_service.mark_failed(run_id=item.run_id)
                return StageExecutionResult(
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    source_id=item.source_id,
                    status="failed",
                    attempts=attempts,
                    failure_classification=failure_classification,
                )

        raise RuntimeError("stage execution exceeded retry policy unexpectedly")

    def _record_ingest_attempt(
        self,
        *,
        stage_name: str,
        source_id: str,
        succeeded: bool,
        failure_reason: str | None,
    ) -> None:
        if stage_name != "ingest" or self._source_health_repository is None:
            return
        self._source_health_repository.record_ingest_attempt(
            source_id=source_id,
            succeeded=succeeded,
            failure_reason=failure_reason,
        )

    def _log_stage_event(
        self,
        *,
        event_name: str,
        stage_name: str,
        outcome: str,
        item: StageWorkItem,
        attempt: int,
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        log_stage_name = _pipeline_log_stage_name(stage_name)
        event: dict[str, object] = {
            "event_name": event_name,
            "city_id": item.city_id,
            "meeting_id": item.meeting_id,
            "run_id": item.run_id,
            "dedupe_key": _stage_dedupe_key(stage_name=log_stage_name, item=item),
            "stage": log_stage_name,
            "outcome": outcome,
            "attempt": attempt,
        }
        if error_code is not None:
            event["error_code"] = error_code
        if error_message is not None:
            event["error_message"] = error_message
        logger.info(event_name, extra={"event": event})


def _outcome_id(*, stage_name: str, item: StageWorkItem) -> str:
    return f"outcome-{stage_name}-{item.run_id}-{item.meeting_id}"


def _metadata_json(
    *,
    attempts: int,
    source_id: str,
    failure_classification: FailureClassification | None,
    error_type: str | None,
    error_message: str | None,
) -> str:
    return json.dumps(
        {
            "attempts": attempts,
            "source_id": source_id,
            "failure_classification": failure_classification,
            "error_type": error_type,
            "error_message": error_message,
        },
        sort_keys=True,
    )


def _stage_dedupe_key(*, stage_name: str, item: StageWorkItem) -> str:
    return f"pipeline:{stage_name}:{item.run_id}:{item.meeting_id}"


def _pipeline_log_stage_name(stage_name: str) -> str:
    if stage_name == "ingest":
        return "fetch"
    if stage_name == "extract":
        return "parse"
    return stage_name


def _error_code_for_exception(error: Exception) -> str:
    if isinstance(error, TransientStageError):
        return "transient_stage_error"
    if isinstance(error, PermanentStageError):
        return "permanent_stage_error"
    return "unhandled_stage_error"


def _short_error_message(error: Exception, *, max_length: int = 160) -> str:
    normalized = str(error).strip() or type(error).__name__
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."