from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Literal

from councilsense.app.notification_contracts import (
    NOTIFICATION_DELIVERY_STATUS_MODEL,
    NotificationEventMessage,
    consume_notification_event_payload,
)
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


@dataclass(frozen=True)
class NotificationDeliveryWorkerConfig:
    claim_batch_size: int = 50
    retry_backoff_seconds: tuple[int, ...] = (15, 60, 300, 900, 3600)

    def __post_init__(self) -> None:
        if self.claim_batch_size <= 0:
            raise ValueError("claim_batch_size must be > 0")
        if not self.retry_backoff_seconds:
            raise ValueError("retry_backoff_seconds must not be empty")
        if any(value <= 0 for value in self.retry_backoff_seconds):
            raise ValueError("retry_backoff_seconds values must be > 0")


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
        config: NotificationDeliveryWorkerConfig | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._sender = sender
        self._suppression_sink = suppression_sink
        self._config = config or NotificationDeliveryWorkerConfig()
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
                      AND attempt_count < max_attempts
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
                (claim_cutoff, limit),
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

        if attempt_number >= record.max_attempts:
            self._record_terminal_failure(
                record=record,
                attempted_at=attempted_at,
                attempt_number=attempt_number,
                outcome="permanent_failure",
                error_code=error.error_code,
                provider_response_summary=error.provider_response_summary,
            )
            return False

        next_retry_at = attempted_at + timedelta(seconds=self._retry_backoff_seconds(attempt_number=attempt_number))
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
                    payload_json,
                    next_retry_at.isoformat(),
                    attempted_at.isoformat(),
                    error.error_code,
                    error.provider_response_summary,
                    record.id,
                ),
            )

        return True

    def _record_permanent_failure(
        self,
        *,
        record: NotificationOutboxRecord,
        error: NotificationDeliveryError,
    ) -> None:
        self._record_terminal_failure(
            record=record,
            attempted_at=self._now_provider().astimezone(UTC),
            attempt_number=record.attempt_count + 1,
            outcome="permanent_failure",
            error_code=error.error_code,
            provider_response_summary=error.provider_response_summary,
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
        error_code: str,
        provider_response_summary: str,
    ) -> None:
        if not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status="failed"):
            raise ValueError("Invalid transition from sending to failed")

        payload_json = self._updated_payload_json(
            existing_payload_json=record.payload_json,
            next_status="failed",
            attempt_count=attempt_number,
            error_code=error_code,
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
                    outcome,
                    error_code,
                    provider_response_summary,
                    None,
                    attempted_at.isoformat(),
                ),
            )
            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'failed',
                    attempt_count = ?,
                    payload_json = ?,
                    last_attempt_at = ?,
                    error_code = ?,
                    provider_response_summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    attempt_number,
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
        validated = NotificationEventMessage.from_payload(next_payload.to_payload())
        return json.dumps(validated.to_payload(), ensure_ascii=False, separators=(",", ":"))