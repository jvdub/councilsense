from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal

from councilsense.db import (
    ProcessingLifecycleService,
    ProcessingRunRepository,
    RunLifecycleStatus,
    SourceHealthRepository,
)

FailureClassification = Literal["transient", "terminal"]
StageFinalDisposition = Literal["success", "retry", "terminal"]
TerminalReason = Literal["retry_exhausted", "non_retryable"]

PIPELINE_RETRY_POLICY_VERSION = "st029-stage-source-retry-policy.v1"

_DEFAULT_SOURCE_TYPE_BY_STAGE: dict[str, str] = {
    "summarize": "bundle",
    "publish": "bundle",
}

_STAGE_SOURCE_MAX_ATTEMPTS: dict[tuple[str, str], int] = {
    ("ingest", "minutes"): 4,
    ("ingest", "agenda"): 3,
    ("ingest", "packet"): 2,
    ("ingest", "unknown"): 2,
    ("extract", "minutes"): 3,
    ("extract", "agenda"): 2,
    ("extract", "packet"): 2,
    ("extract", "unknown"): 2,
    ("summarize", "bundle"): 2,
    ("publish", "bundle"): 3,
}


logger = logging.getLogger(__name__)


class TransientStageError(RuntimeError):
    pass


class PermanentStageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedStageRetryPolicy:
    stage_name: str
    source_type: str
    max_attempts: int
    policy_version: str

    @property
    def matrix_key(self) -> str:
        return f"{self.stage_name}:{self.source_type}"


@dataclass(frozen=True)
class StageFailureDecision:
    failure_classification: FailureClassification
    disposition: StageFinalDisposition
    terminal_reason: TerminalReason | None
    error_code: str


def resolve_stage_retry_policy(
    *,
    stage_name: str,
    source_type: str | None,
    retry_policy: "StageRetryPolicy | None" = None,
) -> ResolvedStageRetryPolicy:
    normalized_source_type = _normalize_source_type(stage_name=stage_name, source_type=source_type)
    base_max_attempts = _STAGE_SOURCE_MAX_ATTEMPTS.get(
        (stage_name, normalized_source_type),
        _STAGE_SOURCE_MAX_ATTEMPTS.get((stage_name, "unknown"), 1),
    )
    if retry_policy is not None:
        base_max_attempts = min(base_max_attempts, retry_policy.max_attempts)
    return ResolvedStageRetryPolicy(
        stage_name=stage_name,
        source_type=normalized_source_type,
        max_attempts=base_max_attempts,
        policy_version=PIPELINE_RETRY_POLICY_VERSION,
    )


def classify_stage_error(
    *,
    error: Exception,
    policy: ResolvedStageRetryPolicy,
    attempt_number: int,
) -> StageFailureDecision:
    error_code = _error_code_for_exception(error)
    if _is_transient_error(error=error, policy=policy):
        if attempt_number < policy.max_attempts:
            return StageFailureDecision(
                failure_classification="transient",
                disposition="retry",
                terminal_reason=None,
                error_code=error_code,
            )
        return StageFailureDecision(
            failure_classification="transient",
            disposition="terminal",
            terminal_reason="retry_exhausted",
            error_code=error_code,
        )
    return StageFailureDecision(
        failure_classification="terminal",
        disposition="terminal",
        terminal_reason="non_retryable",
        error_code=error_code,
    )


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
    source_type: str | None = None
    payload_references: dict[str, str] | None = None
    triage_metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class StageExecutionResult:
    run_id: str
    city_id: str
    meeting_id: str
    source_id: str
    status: RunLifecycleStatus
    attempts: int
    failure_classification: FailureClassification | None
    final_disposition: StageFinalDisposition
    max_attempts: int
    retry_policy_version: str


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
        resolved_policy = resolve_stage_retry_policy(
            stage_name=stage_name,
            source_type=item.source_type,
            retry_policy=self._retry_policy,
        )
        existing_outcome = self._repository.get_stage_outcome(
            run_id=item.run_id,
            city_id=item.city_id,
            meeting_id=item.meeting_id,
            stage_name=stage_name,
        )
        prior_attempts = _existing_attempt_count(existing_outcome=existing_outcome, item=item)
        attempts = prior_attempts

        while attempts < resolved_policy.max_attempts:
            attempts += 1
            self._log_stage_event(
                event_name="pipeline_stage_started",
                stage_name=stage_name,
                outcome="retry" if attempts > 1 else "success",
                item=item,
                attempt=attempts,
                max_attempts=resolved_policy.max_attempts,
                failure_classification=None,
                retry_policy_version=resolved_policy.policy_version,
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
                        existing_metadata_json=existing_outcome.metadata_json if existing_outcome is not None else None,
                        stage_name=stage_name,
                        attempts=attempts,
                        max_attempts=resolved_policy.max_attempts,
                        source_id=item.source_id,
                        source_type=resolved_policy.source_type,
                        failure_classification=None,
                        final_disposition="success",
                        terminal_reason=None,
                        retry_policy_version=resolved_policy.policy_version,
                        error_type=None,
                        error_message=None,
                        payload_references=_normalize_payload_references(item.payload_references),
                        triage_metadata=None,
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
                    max_attempts=resolved_policy.max_attempts,
                    failure_classification=None,
                    retry_policy_version=resolved_policy.policy_version,
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
                    final_disposition="success",
                    max_attempts=resolved_policy.max_attempts,
                    retry_policy_version=resolved_policy.policy_version,
                )
            except Exception as error:
                decision = classify_stage_error(
                    error=error,
                    policy=resolved_policy,
                    attempt_number=attempts,
                )
                if decision.disposition == "retry":
                    self._log_stage_event(
                        event_name="pipeline_stage_error",
                        stage_name=stage_name,
                        outcome="retry",
                        item=item,
                        attempt=attempts,
                        max_attempts=resolved_policy.max_attempts,
                        failure_classification=decision.failure_classification,
                        retry_policy_version=resolved_policy.policy_version,
                        error_code=decision.error_code,
                        error_message=_short_error_message(error),
                    )
                    continue

                self._record_ingest_attempt(
                    stage_name=stage_name,
                    source_id=item.source_id,
                    succeeded=False,
                    failure_reason=f"{type(error).__name__}: {error}",
                )

                terminal_transitioned_at = _utc_now_timestamp()
                triage_metadata = _terminal_triage_metadata(
                    item=item,
                    stage_name=stage_name,
                    policy=resolved_policy,
                    decision=decision,
                    attempts=attempts,
                    error=error,
                )

                outcome_record = self._repository.upsert_stage_outcome(
                    outcome_id=_outcome_id(stage_name=stage_name, item=item),
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    stage_name=stage_name,
                    status="failed",
                    metadata_json=_metadata_json(
                        existing_metadata_json=existing_outcome.metadata_json if existing_outcome is not None else None,
                        stage_name=stage_name,
                        attempts=attempts,
                        max_attempts=resolved_policy.max_attempts,
                        source_id=item.source_id,
                        source_type=resolved_policy.source_type,
                        failure_classification=decision.failure_classification,
                        final_disposition=decision.disposition,
                        terminal_reason=decision.terminal_reason,
                        retry_policy_version=resolved_policy.policy_version,
                        error_type=type(error).__name__,
                        error_message=str(error),
                        payload_references=_normalize_payload_references(item.payload_references),
                        triage_metadata=triage_metadata,
                    ),
                    started_at=None,
                    finished_at=None,
                )
                self._repository.record_pipeline_dlq_entry(
                    run_id=item.run_id,
                    city_id=item.city_id,
                    meeting_id=item.meeting_id,
                    stage_name=stage_name,
                    source_id=item.source_id,
                    source_type=resolved_policy.source_type,
                    stage_outcome_id=outcome_record.id,
                    failure_classification=decision.failure_classification,
                    terminal_reason=decision.terminal_reason or "non_retryable",
                    retry_policy_version=resolved_policy.policy_version,
                    terminal_attempt_number=attempts,
                    max_attempts=resolved_policy.max_attempts,
                    error_code=decision.error_code,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    payload_references=_normalize_payload_references(item.payload_references),
                    triage_metadata=triage_metadata,
                    terminal_transitioned_at=terminal_transitioned_at,
                )
                self._log_stage_event(
                    event_name="pipeline_stage_error",
                    stage_name=stage_name,
                    outcome="failure",
                    item=item,
                    attempt=attempts,
                    max_attempts=resolved_policy.max_attempts,
                    failure_classification=decision.failure_classification,
                    retry_policy_version=resolved_policy.policy_version,
                    error_code=decision.error_code,
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
                    failure_classification=decision.failure_classification,
                    final_disposition=decision.disposition,
                    max_attempts=resolved_policy.max_attempts,
                    retry_policy_version=resolved_policy.policy_version,
                )

        return _result_from_exhausted_attempts(
            repository=self._repository,
            lifecycle_service=self._lifecycle_service,
            stage_name=stage_name,
            item=item,
            policy=resolved_policy,
        )

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
        max_attempts: int,
        failure_classification: FailureClassification | None,
        retry_policy_version: str,
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
            "max_attempts": max_attempts,
            "retry_policy_version": retry_policy_version,
            "source_type": _normalize_source_type(stage_name=stage_name, source_type=item.source_type),
        }
        if failure_classification is not None:
            event["failure_classification"] = failure_classification
        if error_code is not None:
            event["error_code"] = error_code
        if error_message is not None:
            event["error_message"] = error_message
        logger.info(event_name, extra={"event": event})


def _outcome_id(*, stage_name: str, item: StageWorkItem) -> str:
    return f"outcome-{stage_name}-{item.run_id}-{item.meeting_id}"


def _metadata_json(
    *,
    existing_metadata_json: str | None,
    stage_name: str,
    attempts: int,
    max_attempts: int,
    source_id: str,
    source_type: str,
    failure_classification: FailureClassification | None,
    final_disposition: StageFinalDisposition,
    terminal_reason: TerminalReason | None,
    retry_policy_version: str,
    error_type: str | None,
    error_message: str | None,
    payload_references: dict[str, str],
    triage_metadata: dict[str, object] | None,
) -> str:
    metadata = _load_metadata(existing_metadata_json)
    source_attempts = metadata.setdefault("source_attempts", {})
    source_attempts[source_id] = {
        "source_id": source_id,
        "source_type": source_type,
        "stage_name": stage_name,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "failure_classification": failure_classification,
        "final_disposition": final_disposition,
        "terminal_reason": terminal_reason,
        "retry_policy_version": retry_policy_version,
        "error_type": error_type,
        "error_message": error_message,
        "policy_key": f"{stage_name}:{source_type}",
        "payload_references": payload_references,
        "triage_metadata": triage_metadata,
    }
    metadata.update(
        {
            "attempts": attempts,
            "max_attempts": max_attempts,
            "source_id": source_id,
            "source_type": source_type,
            "failure_classification": failure_classification,
            "final_disposition": final_disposition,
            "terminal_reason": terminal_reason,
            "retry_policy_version": retry_policy_version,
            "policy_key": f"{stage_name}:{source_type}",
            "error_type": error_type,
            "error_message": error_message,
            "payload_references": payload_references,
            "triage_metadata": triage_metadata,
        }
    )
    return json.dumps(metadata, sort_keys=True)


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
        return "terminal_stage_error"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, ConnectionError):
        return "connection_error"
    if isinstance(error, LookupError):
        return "lookup_error"
    if isinstance(error, ValueError):
        return "value_error"
    return "unhandled_stage_error"


def _short_error_message(error: Exception, *, max_length: int = 160) -> str:
    normalized = str(error).strip() or type(error).__name__
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."


def _normalize_source_type(*, stage_name: str, source_type: str | None) -> str:
    normalized = (source_type or "").strip().lower()
    if normalized:
        return normalized
    return _DEFAULT_SOURCE_TYPE_BY_STAGE.get(stage_name, "unknown")


def _is_transient_error(*, error: Exception, policy: ResolvedStageRetryPolicy) -> bool:
    if isinstance(error, TransientStageError):
        return True
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if policy.stage_name == "ingest" and policy.source_type == "minutes" and isinstance(error, LookupError):
        return True
    return False


def _load_metadata(existing_metadata_json: str | None) -> dict[str, Any]:
    if not existing_metadata_json:
        return {}
    try:
        parsed = json.loads(existing_metadata_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    source_attempts = parsed.get("source_attempts")
    if not isinstance(source_attempts, dict):
        parsed["source_attempts"] = {}
    return parsed


def _normalize_payload_references(payload_references: dict[str, str] | None) -> dict[str, str]:
    if payload_references is None:
        return {}
    normalized: dict[str, str] = {}
    for key, value in payload_references.items():
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def _terminal_triage_metadata(
    *,
    item: StageWorkItem,
    stage_name: str,
    policy: ResolvedStageRetryPolicy,
    decision: StageFailureDecision,
    attempts: int,
    error: Exception,
) -> dict[str, object]:
    triage_metadata = _normalize_json_mapping(item.triage_metadata)
    triage_metadata.update(
        {
            "boundary": "terminal",
            "run_id": item.run_id,
            "city_id": item.city_id,
            "meeting_id": item.meeting_id,
            "stage_name": stage_name,
            "source_id": item.source_id,
            "source_type": policy.source_type,
            "policy_key": policy.matrix_key,
            "retry_policy_version": policy.policy_version,
            "failure_classification": decision.failure_classification,
            "terminal_reason": decision.terminal_reason,
            "attempts": attempts,
            "max_attempts": policy.max_attempts,
            "error_code": decision.error_code,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
    )
    return triage_metadata


def _normalize_json_mapping(payload: dict[str, object] | None) -> dict[str, object]:
    if payload is None:
        return {}
    normalized: dict[str, object] = {}
    for key, value in payload.items():
        normalized_key = key.strip()
        if not normalized_key:
            continue
        normalized[normalized_key] = _normalize_json_value(value)
    return normalized


def _normalize_json_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            normalized_key = key.strip()
            if not normalized_key:
                continue
            normalized[normalized_key] = _normalize_json_value(child)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(child) for child in value]
    return str(value)


def _utc_now_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _existing_attempt_count(*, existing_outcome: object, item: StageWorkItem) -> int:
    if existing_outcome is None:
        return 0
    metadata_json = getattr(existing_outcome, "metadata_json", None)
    metadata = _load_metadata(metadata_json)
    source_attempts = metadata.get("source_attempts")
    if isinstance(source_attempts, dict):
        candidate = source_attempts.get(item.source_id)
        if isinstance(candidate, dict):
            attempts = candidate.get("attempts")
            if isinstance(attempts, int) and attempts >= 0:
                return attempts
    legacy_source_id = metadata.get("source_id")
    legacy_attempts = metadata.get("attempts")
    if legacy_source_id == item.source_id and isinstance(legacy_attempts, int) and legacy_attempts >= 0:
        return legacy_attempts
    return 0


def _result_from_exhausted_attempts(
    *,
    repository: ProcessingRunRepository,
    lifecycle_service: ProcessingLifecycleService,
    stage_name: str,
    item: StageWorkItem,
    policy: ResolvedStageRetryPolicy,
) -> StageExecutionResult:
    existing_outcome = repository.get_stage_outcome(
        run_id=item.run_id,
        city_id=item.city_id,
        meeting_id=item.meeting_id,
        stage_name=stage_name,
    )
    attempts = _existing_attempt_count(existing_outcome=existing_outcome, item=item)
    metadata = _load_metadata(existing_outcome.metadata_json if existing_outcome is not None else None)
    source_attempts = metadata.get("source_attempts", {})
    source_metadata = source_attempts.get(item.source_id) if isinstance(source_attempts, dict) else None
    failure_classification = "terminal"
    if isinstance(source_metadata, dict) and source_metadata.get("failure_classification") in {"transient", "terminal"}:
        failure_classification = source_metadata["failure_classification"]

    if existing_outcome is not None and existing_outcome.status == "processed":
        return StageExecutionResult(
            run_id=item.run_id,
            city_id=item.city_id,
            meeting_id=item.meeting_id,
            source_id=item.source_id,
            status="processed",
            attempts=attempts,
            failure_classification=None,
            final_disposition="success",
            max_attempts=policy.max_attempts,
            retry_policy_version=policy.policy_version,
        )

    lifecycle_service.mark_failed(run_id=item.run_id)
    return StageExecutionResult(
        run_id=item.run_id,
        city_id=item.city_id,
        meeting_id=item.meeting_id,
        source_id=item.source_id,
        status="failed",
        attempts=attempts,
        failure_classification=failure_classification,
        final_disposition="terminal",
        max_attempts=policy.max_attempts,
        retry_policy_version=policy.policy_version,
    )