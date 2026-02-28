from __future__ import annotations

import json
import logging
import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Literal

from councilsense.app.notification_contracts import (
    NOTIFICATION_DELIVERY_STATUS_MODEL,
    NotificationEventMessage,
    consume_notification_event_payload,
)
from councilsense.app.settings import get_settings
from councilsense.db.notifications import NotificationOutboxRecord


class NotificationDeliveryError(RuntimeError):
    def __init__(
        self,
        *,
        classification: Literal["transient", "permanent", "invalid_subscription", "expired_subscription"],
        error_code: str,
        provider_response_summary: str,
    ) -> None:
        self.classification = classification
        self.error_code = error_code
        self.provider_response_summary = provider_response_summary
        super().__init__(provider_response_summary)


class RetryableDeliveryError(NotificationDeliveryError):
    def __init__(self, *, error_code: str, provider_response_summary: str) -> None:
        super().__init__(
            classification="transient",
            error_code=error_code,
            provider_response_summary=provider_response_summary,
        )


class PermanentDeliveryError(NotificationDeliveryError):
    def __init__(self, *, error_code: str, provider_response_summary: str) -> None:
        super().__init__(
            classification="permanent",
            error_code=error_code,
            provider_response_summary=provider_response_summary,
        )


class InvalidSubscriptionDeliveryError(NotificationDeliveryError):
    def __init__(self, *, error_code: str, provider_response_summary: str) -> None:
        super().__init__(
            classification="invalid_subscription",
            error_code=error_code,
            provider_response_summary=provider_response_summary,
        )


class ExpiredSubscriptionDeliveryError(NotificationDeliveryError):
    def __init__(self, *, error_code: str, provider_response_summary: str) -> None:
        super().__init__(
            classification="expired_subscription",
            error_code=error_code,
            provider_response_summary=provider_response_summary,
        )


NotificationSender = Callable[[NotificationOutboxRecord], None]
SubscriptionSuppressionSink = Callable[[str, Literal["invalid_subscription", "expired_subscription"]], None]
NotificationMetricEmitter = Callable[[str, str, str, float], None]

_NOTIFY_DELIVER_STAGE = "notify_deliver"
_NOTIFY_DELIVERY_COUNTER = "councilsense_notifications_delivery_events_total"
_NOTIFY_DELIVERY_DURATION = "councilsense_notifications_delivery_duration_seconds"
_UNKNOWN_RUN_ID = "run-unknown"

logger = logging.getLogger(__name__)


def validate_worker_startup_environment() -> None:
    get_settings(service_name="worker")


@dataclass(frozen=True)
class NotificationDeliveryWorkerConfig:
    claim_batch_size: int = 50
    max_attempts: int = 5
    retry_backoff_seconds: tuple[int, ...] = (15, 60, 300, 900, 3600)
    retry_jitter_factor: float = 0.0
    retry_policy_version: str | None = None

    def __post_init__(self) -> None:
        if self.claim_batch_size <= 0:
            raise ValueError("claim_batch_size must be > 0")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if not self.retry_backoff_seconds:
            raise ValueError("retry_backoff_seconds must not be empty")
        if any(current < previous for previous, current in zip(self.retry_backoff_seconds, self.retry_backoff_seconds[1:])):
            raise ValueError("retry_backoff_seconds must be monotonic non-decreasing")
        if any(value <= 0 for value in self.retry_backoff_seconds):
            raise ValueError("retry_backoff_seconds values must be > 0")
        if not 0.0 <= self.retry_jitter_factor <= 1.0:
            raise ValueError("retry_jitter_factor must be in [0.0, 1.0]")
        if self.retry_policy_version is not None and not self.retry_policy_version.strip():
            raise ValueError("retry_policy_version must be non-empty when provided")

    @property
    def effective_policy_version(self) -> str:
        if self.retry_policy_version is not None:
            return self.retry_policy_version.strip()
        return _derive_retry_policy_version(
            max_attempts=self.max_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
            retry_jitter_factor=self.retry_jitter_factor,
        )


def _default_worker_config() -> NotificationDeliveryWorkerConfig:
    settings = get_settings(service_name="worker")
    policy = settings.notification_retry_policy
    return NotificationDeliveryWorkerConfig(
        claim_batch_size=50,
        max_attempts=policy.max_attempts,
        retry_backoff_seconds=policy.backoff_seconds,
        retry_jitter_factor=policy.jitter_factor,
        retry_policy_version=policy.version,
    )


@dataclass(frozen=True)
class NotificationDeliveryRunResult:
    claimed_count: int
    sent_count: int
    retried_count: int
    failed_count: int
    suppressed_count: int


class NotificationDeliveryWorker:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        sender: NotificationSender,
        suppression_sink: SubscriptionSuppressionSink | None = None,
        metric_emitter: NotificationMetricEmitter | None = None,
        config: NotificationDeliveryWorkerConfig | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._sender = sender
        self._suppression_sink = suppression_sink
        self._metric_emitter = metric_emitter
        self._config = config or _default_worker_config()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def run_once(self) -> NotificationDeliveryRunResult:
        claimed = self._claim_due_rows(limit=self._config.claim_batch_size)
        sent_count = 0
        retried_count = 0
        failed_count = 0
        suppressed_count = 0

        for record in claimed:
            try:
                self._sender(record)
            except NotificationDeliveryError as exc:
                if exc.classification == "transient":
                    if self._record_retryable_failure(record=record, error=exc):
                        retried_count += 1
                    else:
                        failed_count += 1
                    continue

                if exc.classification == "permanent":
                    self._record_permanent_failure(record=record, error=exc)
                    failed_count += 1
                    continue

                if exc.classification == "invalid_subscription":
                    self._record_subscription_terminal_status(
                        record=record,
                        error=exc,
                        status="invalid_subscription",
                    )
                    suppressed_count += 1
                    continue

                self._record_subscription_terminal_status(
                    record=record,
                    error=exc,
                    status="expired_subscription",
                )
                suppressed_count += 1
                continue

            self._record_success(record=record)
            sent_count += 1

        return NotificationDeliveryRunResult(
            claimed_count=len(claimed),
            sent_count=sent_count,
            retried_count=retried_count,
            failed_count=failed_count,
            suppressed_count=suppressed_count,
        )

    def _claim_due_rows(self, *, limit: int) -> tuple[NotificationOutboxRecord, ...]:
        claim_cutoff = self._now_provider().astimezone(UTC).isoformat()

        with self._connection:
            rows = self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'sending',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT id
                    FROM notification_outbox
                    WHERE status IN ('queued', 'failed')
                                            AND attempt_count < MIN(max_attempts, ?)
                      AND next_retry_at <= ?
                    ORDER BY next_retry_at ASC, created_at ASC
                    LIMIT ?
                )
                RETURNING
                    id,
                    user_id,
                    meeting_id,
                    city_id,
                    notification_type,
                    dedupe_key,
                    payload_json,
                    status,
                    attempt_count,
                    max_attempts,
                    next_retry_at,
                    last_attempt_at,
                    error_code,
                    provider_response_summary,
                    subscription_id,
                    sent_at,
                    created_at,
                    updated_at
                """,
                (self._config.max_attempts, claim_cutoff, limit),
            ).fetchall()

        return tuple(self._row_to_outbox_record(row=row) for row in rows)

    def _record_success(self, *, record: NotificationOutboxRecord) -> None:
        attempted_at = self._now_provider().astimezone(UTC)
        attempt_number = record.attempt_count + 1
        payload_json = self._updated_payload_json(
            existing_payload_json=record.payload_json,
            next_status="sent",
            attempt_count=attempt_number,
            error_code=None,
        )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO notification_delivery_attempts (
                    outbox_id,
                    attempt_number,
                    outcome,
                    error_code,
                    provider_response_summary,
                    next_retry_at,
                    attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    attempt_number,
                    "success",
                    None,
                    None,
                    None,
                    attempted_at.isoformat(),
                ),
            )
            self._emit_delivery_outcome(record=record, outcome="success", observed_at=attempted_at)
            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'sent',
                    attempt_count = ?,
                    payload_json = ?,
                    last_attempt_at = ?,
                    sent_at = ?,
                    error_code = NULL,
                    provider_response_summary = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    attempt_number,
                    payload_json,
                    attempted_at.isoformat(),
                    attempted_at.isoformat(),
                    record.id,
                ),
            )

    def _record_retryable_failure(
        self,
        *,
        record: NotificationOutboxRecord,
        error: NotificationDeliveryError,
    ) -> bool:
        attempted_at = self._now_provider().astimezone(UTC)
        attempt_number = record.attempt_count + 1
        effective_max_attempts = self._effective_max_attempts(record.max_attempts)

        if attempt_number >= effective_max_attempts:
            self._record_terminal_failure(
                record=record,
                attempted_at=attempted_at,
                attempt_number=attempt_number,
                outcome="permanent_failure",
                failure_classification="transient",
                error_code=error.error_code,
                provider_response_summary=error.provider_response_summary,
                effective_max_attempts=effective_max_attempts,
            )
            return False

        next_retry_at = attempted_at + timedelta(
            seconds=self._retry_delay_seconds(record=record, attempt_number=attempt_number)
        )
        payload_json = self._updated_payload_json(
            existing_payload_json=record.payload_json,
            next_status="failed",
            attempt_count=attempt_number,
            error_code=error.error_code,
        )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO notification_delivery_attempts (
                    outbox_id,
                    attempt_number,
                    outcome,
                    error_code,
                    provider_response_summary,
                    next_retry_at,
                    attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    attempt_number,
                    "retryable_failure",
                    error.error_code,
                    error.provider_response_summary,
                    next_retry_at.isoformat(),
                    attempted_at.isoformat(),
                ),
            )
            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'failed',
                    attempt_count = ?,
                    max_attempts = ?,
                    payload_json = ?,
                    next_retry_at = ?,
                    last_attempt_at = ?,
                    error_code = ?,
                    provider_response_summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    attempt_number,
                    effective_max_attempts,
                    payload_json,
                    next_retry_at.isoformat(),
                    attempted_at.isoformat(),
                    error.error_code,
                    error.provider_response_summary,
                    record.id,
                ),
            )

        self._emit_delivery_outcome(record=record, outcome="retry", error=error, observed_at=attempted_at)
        return True

    def _record_permanent_failure(
        self,
        *,
        record: NotificationOutboxRecord,
        error: NotificationDeliveryError,
    ) -> None:
        effective_max_attempts = self._effective_max_attempts(record.max_attempts)
        self._record_terminal_failure(
            record=record,
            attempted_at=self._now_provider().astimezone(UTC),
            attempt_number=record.attempt_count + 1,
            outcome="permanent_failure",
            failure_classification="permanent",
            error_code=error.error_code,
            provider_response_summary=error.provider_response_summary,
            effective_max_attempts=effective_max_attempts,
        )

    def _record_subscription_terminal_status(
        self,
        *,
        record: NotificationOutboxRecord,
        error: NotificationDeliveryError,
        status: Literal["invalid_subscription", "expired_subscription"],
    ) -> None:
        attempted_at = self._now_provider().astimezone(UTC)
        attempt_number = record.attempt_count + 1

        if not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status=status):
            raise ValueError(f"Invalid transition from sending to {status}")

        payload_json = self._updated_payload_json(
            existing_payload_json=record.payload_json,
            next_status=status,
            attempt_count=attempt_number,
            error_code=error.error_code,
        )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO notification_delivery_attempts (
                    outbox_id,
                    attempt_number,
                    outcome,
                    error_code,
                    provider_response_summary,
                    next_retry_at,
                    attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    attempt_number,
                    status,
                    error.error_code,
                    error.provider_response_summary,
                    None,
                    attempted_at.isoformat(),
                ),
            )

            self._emit_delivery_outcome(record=record, outcome=status, error=error, observed_at=attempted_at)
            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = ?,
                    attempt_count = ?,
                    payload_json = ?,
                    last_attempt_at = ?,
                    error_code = ?,
                    provider_response_summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    attempt_number,
                    payload_json,
                    attempted_at.isoformat(),
                    error.error_code,
                    error.provider_response_summary,
                    record.id,
                ),
            )

        if self._suppression_sink is not None and record.subscription_id is not None:
            self._suppression_sink(record.subscription_id, status)

    def _record_terminal_failure(
        self,
        *,
        record: NotificationOutboxRecord,
        attempted_at: datetime,
        attempt_number: int,
        outcome: Literal["permanent_failure"],
        failure_classification: Literal["transient", "permanent", "unknown"],
        error_code: str,
        provider_response_summary: str,
        effective_max_attempts: int,
    ) -> None:
        if not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status="dlq"):
            raise ValueError("Invalid transition from sending to dlq")

        payload_json = self._updated_payload_json(
            existing_payload_json=record.payload_json,
            next_status="dlq",
            attempt_count=attempt_number,
            error_code=error_code,
        )
        run_id = _extract_optional_run_id(payload=json.loads(record.payload_json))
        source_id = _extract_optional_source_id(payload=json.loads(record.payload_json))

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO notification_delivery_attempts (
                    outbox_id,
                    attempt_number,
                    outcome,
                    error_code,
                    provider_response_summary,
                    next_retry_at,
                    attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(outbox_id, attempt_number) DO NOTHING
                """,
                (
                    record.id,
                    attempt_number,
                    outcome,
                    error_code,
                    provider_response_summary,
                    None,
                    attempted_at.isoformat(),
                ),
            )

            self._connection.execute(
                """
                INSERT INTO notification_delivery_dlq (
                    outbox_id,
                    notification_id,
                    message_id,
                    city_id,
                    source_id,
                    run_id,
                    meeting_id,
                    user_id,
                    notification_type,
                    failure_classification,
                    failure_reason_code,
                    failure_reason_summary,
                    terminal_attempt_number,
                    terminal_attempted_at,
                    terminal_transitioned_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(outbox_id) DO NOTHING
                """,
                (
                    record.id,
                    record.id,
                    record.dedupe_key,
                    record.city_id,
                    source_id,
                    run_id,
                    record.meeting_id,
                    record.user_id,
                    record.notification_type,
                    failure_classification,
                    error_code,
                    provider_response_summary,
                    attempt_number,
                    attempted_at.isoformat(),
                    attempted_at.isoformat(),
                ),
            )

            self._emit_delivery_outcome(
                record=record,
                outcome="failure",
                error_code=error_code,
                error_summary=provider_response_summary,
                observed_at=attempted_at,
            )
            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'dlq',
                    attempt_count = ?,
                    max_attempts = ?,
                    payload_json = ?,
                    last_attempt_at = ?,
                    error_code = ?,
                    provider_response_summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    attempt_number,
                    effective_max_attempts,
                    payload_json,
                    attempted_at.isoformat(),
                    error_code,
                    provider_response_summary,
                    record.id,
                ),
            )

    def _retry_backoff_seconds(self, *, attempt_number: int) -> int:
        index = min(max(attempt_number - 1, 0), len(self._config.retry_backoff_seconds) - 1)
        return self._config.retry_backoff_seconds[index]

    def _retry_delay_seconds(self, *, record: NotificationOutboxRecord, attempt_number: int) -> int:
        base_seconds = self._retry_backoff_seconds(attempt_number=attempt_number)
        jitter_seconds = self._retry_jitter_seconds(
            dedupe_key=record.dedupe_key,
            attempt_number=attempt_number,
            base_seconds=base_seconds,
        )
        return max(base_seconds + jitter_seconds, 1)

    def _retry_jitter_seconds(self, *, dedupe_key: str, attempt_number: int, base_seconds: int) -> int:
        if self._config.retry_jitter_factor <= 0.0:
            return 0

        jitter_window = max(int(round(base_seconds * self._config.retry_jitter_factor)), 1)
        digest = hashlib.sha256(
            f"{dedupe_key}:{attempt_number}:{self._config.effective_policy_version}".encode("utf-8")
        ).digest()
        bucket = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return (bucket % (2 * jitter_window + 1)) - jitter_window

    def _effective_max_attempts(self, outbox_max_attempts: int) -> int:
        if outbox_max_attempts <= 0:
            return self._config.max_attempts
        return min(outbox_max_attempts, self._config.max_attempts)

    @staticmethod
    def _row_to_outbox_record(*, row: sqlite3.Row | tuple[object, ...]) -> NotificationOutboxRecord:
        values = tuple(row)
        return NotificationOutboxRecord(
            id=str(values[0]),
            user_id=str(values[1]),
            meeting_id=str(values[2]),
            city_id=str(values[3]),
            notification_type=str(values[4]),
            dedupe_key=str(values[5]),
            payload_json=str(values[6]),
            status=str(values[7]),
            attempt_count=int(values[8]),
            max_attempts=int(values[9]),
            next_retry_at=str(values[10]),
            last_attempt_at=str(values[11]) if values[11] is not None else None,
            error_code=str(values[12]) if values[12] is not None else None,
            provider_response_summary=str(values[13]) if values[13] is not None else None,
            subscription_id=str(values[14]) if values[14] is not None else None,
            sent_at=str(values[15]) if values[15] is not None else None,
            created_at=str(values[16]),
            updated_at=str(values[17]),
        )

    def _updated_payload_json(
        self,
        *,
        existing_payload_json: str,
        next_status: str,
        attempt_count: int,
        error_code: str | None,
    ) -> str:
        parsed_raw = json.loads(existing_payload_json)
        if not isinstance(parsed_raw, dict):
            raise ValueError("notification payload_json must contain a JSON object")

        parsed: NotificationEventMessage = consume_notification_event_payload(parsed_raw)
        if not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(
            current=parsed.delivery_status,
            next_status="sending",
        ) and parsed.delivery_status != "sending":
            raise ValueError(
                f"Invalid contract transition from payload status '{parsed.delivery_status}' to 'sending'"
            )
        if not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status=next_status):
            raise ValueError(f"Invalid contract transition from sending to '{next_status}'")

        next_payload = NotificationEventMessage(
            contract_version=parsed.contract_version,
            user_id=parsed.user_id,
            meeting_id=parsed.meeting_id,
            notification_type=parsed.notification_type,
            dedupe_key=parsed.dedupe_key,
            enqueued_at=parsed.enqueued_at,
            delivery_status=next_status,
            subscription_id=parsed.subscription_id,
            attempt_count=attempt_count,
            error_code=error_code,
        )
        validated_payload = NotificationEventMessage.from_payload(next_payload.to_payload()).to_payload()
        run_id = _extract_optional_run_id(parsed_raw)
        if run_id is not None:
            validated_payload["run_id"] = run_id
        source_id = _extract_optional_source_id(parsed_raw)
        if source_id is not None:
            validated_payload["source_id"] = source_id
        validated_payload["retry_policy_version"] = self._config.effective_policy_version
        return json.dumps(validated_payload, ensure_ascii=False, separators=(",", ":"))

    def _emit_delivery_outcome(
        self,
        *,
        record: NotificationOutboxRecord,
        outcome: Literal["success", "retry", "failure", "invalid_subscription", "expired_subscription"],
        observed_at: datetime,
        error: NotificationDeliveryError | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        resolved_error_code = error.error_code if error is not None else error_code
        resolved_error_summary = error.provider_response_summary if error is not None else error_summary
        run_id = self._extract_run_id(payload_json=record.payload_json)
        latency_seconds = self._delivery_latency_seconds(payload_json=record.payload_json, observed_at=observed_at)

        self._emit_metric(name=_NOTIFY_DELIVERY_COUNTER, stage=_NOTIFY_DELIVER_STAGE, outcome=outcome, value=1.0)
        if latency_seconds is not None:
            self._emit_metric(
                name=_NOTIFY_DELIVERY_DURATION,
                stage=_NOTIFY_DELIVER_STAGE,
                outcome=outcome,
                value=latency_seconds,
            )

        logger.info(
            "notification_delivery_attempt",
            extra={
                "event": {
                    "event_name": "notification_delivery_attempt",
                    "city_id": record.city_id,
                    "meeting_id": record.meeting_id,
                    "run_id": run_id,
                    "dedupe_key": record.dedupe_key,
                    "stage": _NOTIFY_DELIVER_STAGE,
                    "outcome": outcome,
                    "attempt_count": record.attempt_count + 1,
                    "retry_policy_version": self._config.effective_policy_version,
                    "error_code": resolved_error_code,
                    "error_summary": _normalize_error_summary(resolved_error_summary),
                }
            },
        )

    def _emit_metric(self, *, name: str, stage: str, outcome: str, value: float) -> None:
        if self._metric_emitter is None:
            return
        self._metric_emitter(name, stage, outcome, value)

    def _extract_run_id(self, *, payload_json: str) -> str:
        try:
            parsed = json.loads(payload_json)
        except json.JSONDecodeError:
            return _UNKNOWN_RUN_ID

        if not isinstance(parsed, dict):
            return _UNKNOWN_RUN_ID

        raw_value = parsed.get("run_id")
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            if normalized:
                return normalized
        return _UNKNOWN_RUN_ID

    def _delivery_latency_seconds(self, *, payload_json: str, observed_at: datetime) -> float | None:
        try:
            parsed = json.loads(payload_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        message = consume_notification_event_payload(parsed)
        latency_seconds = (observed_at.astimezone(UTC) - message.enqueued_at.astimezone(UTC)).total_seconds()
        return max(latency_seconds, 0.0)


def _normalize_error_summary(raw_summary: str | None) -> str | None:
    if raw_summary is None:
        return None
    summary = " ".join(raw_summary.split())
    if not summary:
        return None
    return summary[:120]


def _extract_optional_run_id(payload: dict[str, object]) -> str | None:
    raw_value = payload.get("run_id")
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    return normalized


def _extract_optional_source_id(payload: dict[str, object]) -> str | None:
    raw_value = payload.get("source_id")
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    return normalized


def _derive_retry_policy_version(
    *,
    max_attempts: int,
    retry_backoff_seconds: tuple[int, ...],
    retry_jitter_factor: float,
) -> str:
    fingerprint_input = (
        f"max={max_attempts}|"
        f"backoff={','.join(str(value) for value in retry_backoff_seconds)}|"
        f"jitter={retry_jitter_factor:.6f}"
    )
    digest = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:12]
    return f"notif-retry-v1-{digest}"