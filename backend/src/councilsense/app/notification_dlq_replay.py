from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4
from collections.abc import Callable

from councilsense.app.notification_contracts import NotificationEventMessage, consume_notification_event_payload


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
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._allow_permanent_invalid_override = allow_permanent_invalid_override
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
                    replay_outbox_id
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

            if existing_replay_outbox_id is not None:
                return self._insert_audit_row(
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

            if failure_classification == "permanent" and not (
                self._allow_permanent_invalid_override and override_permanent_invalid
            ):
                return self._insert_audit_row(
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

            self._connection.execute(
                """
                UPDATE notification_delivery_dlq
                SET
                    replayed_at = ?,
                    replayed_by = ?,
                    replay_idempotency_key = ?,
                    replay_outbox_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    replayed_at,
                    actor_user_id,
                    normalized_key,
                    replay_outbox_id,
                    dlq_id,
                ),
            )

            return self._insert_audit_row(
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
