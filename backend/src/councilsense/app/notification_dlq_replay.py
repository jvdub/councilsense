from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4
from collections.abc import Callable

from councilsense.app.notification_contracts import NotificationEventMessage, consume_notification_event_payload


logger = logging.getLogger(__name__)

NotificationMetricEmitter = Callable[[str, str, str, float], None]

_NOTIFY_DLQ_STAGE = "notify_dlq"
_NOTIFY_REPLAY_STAGE = "notify_dlq_replay"
_NOTIFY_DLQ_BACKLOG_COUNT = "councilsense_notifications_dlq_backlog_count"
_NOTIFY_DLQ_OLDEST_AGE_SECONDS = "councilsense_notifications_dlq_oldest_age_seconds"
_NOTIFY_REPLAY_COUNTER = "councilsense_notifications_dlq_replay_events_total"
_NOTIFY_REPLAY_DUPLICATE_HITS = "councilsense_notifications_dlq_replay_duplicate_prevention_hits_total"
_UNKNOWN_RUN_ID = "run-unknown"


class NotificationDlqReplayNotFoundError(LookupError):
    pass


class NotificationDlqReplayIneligibleError(RuntimeError):
    def __init__(self, *, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class NotificationDlqReplayResult:
    dlq_id: int
    source_outbox_id: str
    replay_outbox_id: str | None
    requeue_correlation_id: str
    replay_idempotency_key: str
    actor_user_id: str
    replay_reason: str
    outcome: str
    outcome_detail: str | None
    created_at: str


class NotificationDlqReplayService:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        allow_permanent_invalid_override: bool,
        metric_emitter: NotificationMetricEmitter | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._allow_permanent_invalid_override = allow_permanent_invalid_override
        self._metric_emitter = metric_emitter
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def replay(
        self,
        *,
        dlq_outbox_id: str,
        replay_idempotency_key: str,
        actor_user_id: str,
        replay_reason: str,
        override_permanent_invalid: bool,
    ) -> NotificationDlqReplayResult:
        normalized_key = replay_idempotency_key.strip()
        normalized_reason = replay_reason.strip()
        if not normalized_key:
            raise ValueError("replay_idempotency_key must be non-empty")
        if not normalized_reason:
            raise ValueError("replay_reason must be non-empty")

        with self._connection:
            existing = self._connection.execute(
                """
                SELECT
                    id,
                    dlq_id,
                    source_outbox_id,
                    replay_outbox_id,
                    requeue_correlation_id,
                    replay_idempotency_key,
                    actor_user_id,
                    replay_reason,
                    outcome,
                    outcome_detail,
                    created_at
                FROM notification_dlq_replay_audit
                WHERE replay_idempotency_key = ?
                """,
                (normalized_key,),
            ).fetchone()
            if existing is not None:
                return self._row_to_result(existing)

            dlq_row = self._connection.execute(
                """
                SELECT
                    id,
                    outbox_id,
                    failure_classification,
                    replay_outbox_id,
                    city_id,
                    source_id,
                    meeting_id,
                    run_id,
                    notification_type
                FROM notification_delivery_dlq
                WHERE outbox_id = ?
                """,
                (dlq_outbox_id,),
            ).fetchone()
            if dlq_row is None:
                raise NotificationDlqReplayNotFoundError(dlq_outbox_id)

            dlq_id = int(dlq_row[0])
            source_outbox_id = str(dlq_row[1])
            failure_classification = str(dlq_row[2])
            existing_replay_outbox_id = str(dlq_row[3]) if dlq_row[3] is not None else None
            city_id = str(dlq_row[4])
            source_id = str(dlq_row[5]) if dlq_row[5] is not None else None
            meeting_id = str(dlq_row[6])
            run_id = str(dlq_row[7]) if dlq_row[7] is not None else _UNKNOWN_RUN_ID
            notification_type = str(dlq_row[8])

            if existing_replay_outbox_id is not None:
                result = self._insert_audit_row(
                    dlq_id=dlq_id,
                    source_outbox_id=source_outbox_id,
                    replay_outbox_id=existing_replay_outbox_id,
                    requeue_correlation_id=f"requeue-correlation-{uuid4().hex}",
                    replay_idempotency_key=normalized_key,
                    actor_user_id=actor_user_id,
                    replay_reason=normalized_reason,
                    outcome="duplicate",
                    outcome_detail="dlq_item_already_replayed",
                )
                self._emit_replay_observability(
                    result=result,
                    city_id=city_id,
                    source_id=source_id,
                    meeting_id=meeting_id,
                    run_id=run_id,
                    notification_type=notification_type,
                )
                return result

            if failure_classification == "permanent" and not (
                self._allow_permanent_invalid_override and override_permanent_invalid
            ):
                result = self._insert_audit_row(
                    dlq_id=dlq_id,
                    source_outbox_id=source_outbox_id,
                    replay_outbox_id=None,
                    requeue_correlation_id=f"requeue-correlation-{uuid4().hex}",
                    replay_idempotency_key=normalized_key,
                    actor_user_id=actor_user_id,
                    replay_reason=normalized_reason,
                    outcome="ineligible",
                    outcome_detail="permanent_failure_requires_policy_override",
                )
                self._emit_replay_observability(
                    result=result,
                    city_id=city_id,
                    source_id=source_id,
                    meeting_id=meeting_id,
                    run_id=run_id,
                    notification_type=notification_type,
                )
                return result

            source_outbox = self._connection.execute(
                """
                SELECT
                    user_id,
                    meeting_id,
                    city_id,
                    notification_type,
                    payload_json,
                    max_attempts,
                    subscription_id
                FROM notification_outbox
                WHERE id = ?
                """,
                (source_outbox_id,),
            ).fetchone()
            if source_outbox is None:
                raise NotificationDlqReplayNotFoundError(dlq_outbox_id)

            replay_outbox_id = source_outbox_id
            replayed_at = self._now_provider().astimezone(UTC).isoformat()
            requeue_correlation_id = f"requeue-correlation-{uuid4().hex}"
            payload_json = self._build_replay_payload_json(
                source_payload_json=str(source_outbox[4]),
                replayed_at=replayed_at,
                requeue_correlation_id=requeue_correlation_id,
            )

            claim_cursor = self._connection.execute(
                """
                UPDATE notification_delivery_dlq
                SET
                    replayed_at = ?,
                    replayed_by = ?,
                    replay_idempotency_key = ?,
                    replay_outbox_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND replay_outbox_id IS NULL
                """,
                (
                    replayed_at,
                    actor_user_id,
                    normalized_key,
                    replay_outbox_id,
                    dlq_id,
                ),
            )
            if claim_cursor.rowcount <= 0:
                existing_replay_row = self._connection.execute(
                    """
                    SELECT replay_outbox_id
                    FROM notification_delivery_dlq
                    WHERE id = ?
                    """,
                    (dlq_id,),
                ).fetchone()
                resolved_replay_outbox_id = (
                    str(existing_replay_row[0])
                    if existing_replay_row is not None and existing_replay_row[0] is not None
                    else source_outbox_id
                )
                result = self._insert_audit_row(
                    dlq_id=dlq_id,
                    source_outbox_id=source_outbox_id,
                    replay_outbox_id=resolved_replay_outbox_id,
                    requeue_correlation_id=f"requeue-correlation-{uuid4().hex}",
                    replay_idempotency_key=normalized_key,
                    actor_user_id=actor_user_id,
                    replay_reason=normalized_reason,
                    outcome="duplicate",
                    outcome_detail="dlq_item_already_replayed",
                )
                self._emit_replay_observability(
                    result=result,
                    city_id=city_id,
                    source_id=source_id,
                    meeting_id=meeting_id,
                    run_id=run_id,
                    notification_type=notification_type,
                )
                return result

            self._connection.execute(
                """
                UPDATE notification_outbox
                SET
                    status = 'queued',
                    attempt_count = 0,
                    payload_json = ?,
                    next_retry_at = ?,
                    last_attempt_at = NULL,
                    error_code = NULL,
                    provider_response_summary = NULL,
                    sent_at = NULL,
                    max_attempts = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    payload_json,
                    replayed_at,
                    int(source_outbox[5]),
                    source_outbox_id,
                ),
            )

            result = self._insert_audit_row(
                dlq_id=dlq_id,
                source_outbox_id=source_outbox_id,
                replay_outbox_id=replay_outbox_id,
                requeue_correlation_id=requeue_correlation_id,
                replay_idempotency_key=normalized_key,
                actor_user_id=actor_user_id,
                replay_reason=normalized_reason,
                outcome="requeued",
                outcome_detail=None,
            )
            self._emit_replay_observability(
                result=result,
                city_id=city_id,
                source_id=source_id,
                meeting_id=meeting_id,
                run_id=run_id,
                notification_type=notification_type,
            )
            return result

    def _emit_replay_observability(
        self,
        *,
        result: NotificationDlqReplayResult,
        city_id: str,
        source_id: str | None,
        meeting_id: str,
        run_id: str,
        notification_type: str,
    ) -> None:
        self._emit_metric(
            name=_NOTIFY_REPLAY_COUNTER,
            stage=_NOTIFY_REPLAY_STAGE,
            outcome=result.outcome,
            value=1.0,
        )
        if result.outcome == "duplicate":
            self._emit_metric(
                name=_NOTIFY_REPLAY_DUPLICATE_HITS,
                stage=_NOTIFY_REPLAY_STAGE,
                outcome="duplicate",
                value=1.0,
            )

        backlog_count, oldest_age_seconds = self._dlq_backlog_snapshot()
        self._emit_metric(
            name=_NOTIFY_DLQ_BACKLOG_COUNT,
            stage=_NOTIFY_DLQ_STAGE,
            outcome="backlog",
            value=float(backlog_count),
        )
        self._emit_metric(
            name=_NOTIFY_DLQ_OLDEST_AGE_SECONDS,
            stage=_NOTIFY_DLQ_STAGE,
            outcome="oldest_age",
            value=oldest_age_seconds,
        )

        logger.info(
            "notification_dlq_replay_attempt",
            extra={
                "event": {
                    "event_name": "notification_dlq_replay_attempt",
                    "city_id": city_id,
                    "meeting_id": meeting_id,
                    "run_id": run_id,
                    "dedupe_key": result.replay_idempotency_key,
                    "stage": _NOTIFY_REPLAY_STAGE,
                    "outcome": result.outcome,
                    "source_id": source_id,
                    "channel": notification_type,
                    "outcome_detail": result.outcome_detail,
                    "requeue_correlation_id": result.requeue_correlation_id,
                }
            },
        )
        logger.info(
            "notification_dlq_backlog_snapshot",
            extra={
                "event": {
                    "event_name": "notification_dlq_backlog_snapshot",
                    "city_id": city_id,
                    "meeting_id": meeting_id,
                    "run_id": run_id,
                    "dedupe_key": result.replay_idempotency_key,
                    "stage": _NOTIFY_DLQ_STAGE,
                    "outcome": "snapshot",
                    "source_id": source_id,
                    "channel": notification_type,
                    "backlog_count": backlog_count,
                    "oldest_age_seconds": oldest_age_seconds,
                }
            },
        )

    def _dlq_backlog_snapshot(self) -> tuple[int, float]:
        row = self._connection.execute(
            """
            SELECT COUNT(*), MIN(terminal_transitioned_at)
            FROM notification_delivery_dlq
            WHERE replayed_at IS NULL
            """
        ).fetchone()
        if row is None:
            return 0, 0.0

        backlog_count = int(row[0])
        oldest_raw = row[1]
        if oldest_raw is None:
            return backlog_count, 0.0

        now = self._now_provider().astimezone(UTC)
        parsed = datetime.fromisoformat(str(oldest_raw))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        oldest_age_seconds = max((now - parsed.astimezone(UTC)).total_seconds(), 0.0)
        return backlog_count, oldest_age_seconds

    def _emit_metric(self, *, name: str, stage: str, outcome: str, value: float) -> None:
        if self._metric_emitter is None:
            return
        self._metric_emitter(name, stage, outcome, value)

    def _insert_audit_row(
        self,
        *,
        dlq_id: int,
        source_outbox_id: str,
        replay_outbox_id: str | None,
        requeue_correlation_id: str,
        replay_idempotency_key: str,
        actor_user_id: str,
        replay_reason: str,
        outcome: str,
        outcome_detail: str | None,
    ) -> NotificationDlqReplayResult:
        try:
            self._connection.execute(
                """
                INSERT INTO notification_dlq_replay_audit (
                    dlq_id,
                    source_outbox_id,
                    replay_outbox_id,
                    requeue_correlation_id,
                    replay_idempotency_key,
                    actor_user_id,
                    replay_reason,
                    outcome,
                    outcome_detail
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dlq_id,
                    source_outbox_id,
                    replay_outbox_id,
                    requeue_correlation_id,
                    replay_idempotency_key,
                    actor_user_id,
                    replay_reason,
                    outcome,
                    outcome_detail,
                ),
            )
        except sqlite3.IntegrityError:
            pass

        row = self._connection.execute(
            """
            SELECT
                id,
                dlq_id,
                source_outbox_id,
                replay_outbox_id,
                requeue_correlation_id,
                replay_idempotency_key,
                actor_user_id,
                replay_reason,
                outcome,
                outcome_detail,
                created_at
            FROM notification_dlq_replay_audit
            WHERE replay_idempotency_key = ?
            """,
            (replay_idempotency_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to fetch replay audit row")
        return self._row_to_result(row)

    @staticmethod
    def _build_replay_payload_json(
        *,
        source_payload_json: str,
        replayed_at: str,
        requeue_correlation_id: str,
    ) -> str:
        source_payload = json.loads(source_payload_json)
        if not isinstance(source_payload, dict):
            raise ValueError("notification payload_json must contain a JSON object")

        parsed = consume_notification_event_payload(source_payload)
        replay_event = NotificationEventMessage(
            contract_version=parsed.contract_version,
            user_id=parsed.user_id,
            meeting_id=parsed.meeting_id,
            notification_type=parsed.notification_type,
            dedupe_key=parsed.dedupe_key,
            enqueued_at=datetime.fromisoformat(replayed_at),
            delivery_status="queued",
            subscription_id=parsed.subscription_id,
            attempt_count=0,
            error_code=None,
        )
        payload = replay_event.to_payload()

        if "run_id" in source_payload:
            payload["run_id"] = source_payload["run_id"]
        if "source_id" in source_payload:
            payload["source_id"] = source_payload["source_id"]
        payload["requeue_correlation_id"] = requeue_correlation_id
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _row_to_result(row: sqlite3.Row | tuple[object, ...]) -> NotificationDlqReplayResult:
        values = tuple(row)
        return NotificationDlqReplayResult(
            dlq_id=int(values[1]),
            source_outbox_id=str(values[2]),
            replay_outbox_id=str(values[3]) if values[3] is not None else None,
            requeue_correlation_id=str(values[4]),
            replay_idempotency_key=str(values[5]),
            actor_user_id=str(values[6]),
            replay_reason=str(values[7]),
            outcome=str(values[8]),
            outcome_detail=str(values[9]) if values[9] is not None else None,
            created_at=str(values[10]),
        )
