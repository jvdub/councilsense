from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Literal

from councilsense.db import (
    ProcessingLifecycleService,
    ProcessingRunRepository,
    RunLifecycleStatus,
    SourceHealthRepository,
)


FailureClassification = Literal["transient", "permanent"]


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