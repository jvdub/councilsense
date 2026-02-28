from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import sqlite3
from typing import Protocol
from uuid import uuid4


DELETION_SLA_DAYS = 30
ACTOR_PROCESSOR = "system:governance-deletion-processor"


class DeletionProfileService(Protocol):
    def apply_governance_deletion(self, *, user_id: str, mode: str) -> None: ...


class GovernanceDeletionNotFoundError(Exception):
    pass


class GovernanceDeletionOwnershipError(Exception):
    pass


@dataclass(frozen=True)
class GovernanceDeletionRequestView:
    id: str
    user_id: str
    idempotency_key: str
    mode: str
    status: str
    reason_code: str | None
    due_at: str | None
    completed_at: str | None
    error_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GovernanceDeletionProcessingResult:
    claimed_count: int
    completed_count: int
    failed_count: int
    breached_sla_count: int


class GovernanceDeletionService:
    def __init__(self, *, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_request(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        mode: str,
        requested_by: str,
        reason_code: str | None = None,
    ) -> GovernanceDeletionRequestView:
        self._ensure_governance_identity(user_id)
        request_id = f"del-{uuid4().hex}"

        try:
            self._connection.execute(
                """
                INSERT INTO governance_deletion_requests (
                    id,
                    user_id,
                    idempotency_key,
                    mode,
                    status,
                    requested_by,
                    reason_code
                )
                VALUES (?, ?, ?, ?, 'requested', ?, ?)
                """,
                (request_id, user_id, idempotency_key, mode, requested_by, reason_code),
            )
        except sqlite3.IntegrityError:
            row = self._connection.execute(
                """
                SELECT id, user_id
                FROM governance_deletion_requests
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise
            existing_request_id, existing_user_id = str(row[0]), str(row[1])
            if existing_user_id != user_id:
                raise GovernanceDeletionOwnershipError
            return self.get_request(user_id=user_id, request_id=existing_request_id)

        return self.get_request(user_id=user_id, request_id=request_id)

    def get_request(self, *, user_id: str, request_id: str) -> GovernanceDeletionRequestView:
        row = self._connection.execute(
            """
            SELECT
                id,
                user_id,
                idempotency_key,
                mode,
                status,
                reason_code,
                due_at,
                completed_at,
                error_code,
                created_at,
                updated_at
            FROM governance_deletion_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise GovernanceDeletionNotFoundError

        request_user_id = str(row[1])
        if request_user_id != user_id:
            raise GovernanceDeletionOwnershipError

        return GovernanceDeletionRequestView(
            id=str(row[0]),
            user_id=request_user_id,
            idempotency_key=str(row[2]),
            mode=str(row[3]),
            status=str(row[4]),
            reason_code=str(row[5]) if row[5] is not None else None,
            due_at=str(row[6]) if row[6] is not None else None,
            completed_at=str(row[7]) if row[7] is not None else None,
            error_code=str(row[8]) if row[8] is not None else None,
            created_at=str(row[9]),
            updated_at=str(row[10]),
        )

    def _ensure_governance_identity(self, user_id: str) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO governance_user_identities (user_id)
            VALUES (?)
            """,
            (user_id,),
        )


class GovernanceDeletionProcessor:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        profile_service: DeletionProfileService,
        now_provider: callable | None = None,
    ) -> None:
        self._connection = connection
        self._profile_service = profile_service
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def run_once(self, *, batch_size: int = 25) -> GovernanceDeletionProcessingResult:
        pending_rows = self._connection.execute(
            """
            SELECT id, user_id, mode, status, due_at
            FROM governance_deletion_requests
            WHERE status IN ('requested', 'failed')
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()

        claimed_count = len(pending_rows)
        completed_count = 0
        failed_count = 0
        breached_sla_count = 0

        for row in pending_rows:
            request_id = str(row[0])
            user_id = str(row[1])
            mode = str(row[2])
            current_status = str(row[3])
            due_at = str(row[4]) if row[4] is not None else None

            if current_status == "requested":
                accepted_at = self._now_provider()
                due_at = (accepted_at + timedelta(days=DELETION_SLA_DAYS)).isoformat()
                self._connection.execute(
                    """
                    UPDATE governance_deletion_requests
                    SET
                        status = 'accepted',
                        requested_by = ?,
                        due_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (ACTOR_PROCESSOR, due_at, request_id),
                )

            self._record_phase_audit_event(
                request_id=request_id,
                phase="before_processing",
                user_id=user_id,
                mode=mode,
                due_at=due_at,
            )

            self._connection.execute(
                """
                UPDATE governance_deletion_requests
                SET status = 'processing', requested_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ACTOR_PROCESSOR, request_id),
            )

            try:
                self._apply_policy(user_id=user_id, mode=mode)
            except Exception:
                self._connection.execute(
                    """
                    UPDATE governance_deletion_requests
                    SET
                        status = 'failed',
                        requested_by = ?,
                        error_code = 'deletion_processing_failed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (ACTOR_PROCESSOR, request_id),
                )
                self._record_phase_audit_event(
                    request_id=request_id,
                    phase="failed",
                    user_id=user_id,
                    mode=mode,
                    due_at=due_at,
                )
                failed_count += 1
                continue

            completed_at = self._now_provider()
            due_at_dt = _parse_utc_datetime(due_at)
            sla_breached = due_at_dt is not None and completed_at > due_at_dt

            self._connection.execute(
                """
                UPDATE governance_deletion_requests
                SET
                    status = 'completed',
                    requested_by = ?,
                    completed_at = ?,
                    error_code = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ACTOR_PROCESSOR, completed_at.isoformat(), request_id),
            )
            self._record_phase_audit_event(
                request_id=request_id,
                phase="after_processing",
                user_id=user_id,
                mode=mode,
                due_at=due_at,
                completed_at=completed_at.isoformat(),
                sla_breached=sla_breached,
            )
            if sla_breached:
                breached_sla_count += 1
            completed_count += 1

        return GovernanceDeletionProcessingResult(
            claimed_count=claimed_count,
            completed_count=completed_count,
            failed_count=failed_count,
            breached_sla_count=breached_sla_count,
        )

    def _apply_policy(self, *, user_id: str, mode: str) -> None:
        self._profile_service.apply_governance_deletion(user_id=user_id, mode=mode)

        if mode == "delete":
            self._connection.execute(
                """
                DELETE FROM notification_outbox
                WHERE user_id = ?
                """,
                (user_id,),
            )
            return

        anonymized_user_id = self._anonymized_user_id(user_id)
        self._connection.execute(
            """
            UPDATE notification_outbox
            SET
                user_id = ?,
                subscription_id = NULL,
                provider_response_summary = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (anonymized_user_id, user_id),
        )

    def _record_phase_audit_event(
        self,
        *,
        request_id: str,
        phase: str,
        user_id: str,
        mode: str,
        due_at: str | None,
        completed_at: str | None = None,
        sla_breached: bool | None = None,
    ) -> None:
        metadata = {
            "processing_phase": phase,
            "mode": mode,
            "target_user_id": user_id,
            "due_at": due_at,
        }
        if completed_at is not None:
            metadata["completed_at"] = completed_at
        if sla_breached is not None:
            metadata["sla_breached"] = sla_breached

        self._connection.execute(
            """
            INSERT INTO governance_audit_events (
                event_type,
                entity_type,
                entity_id,
                actor_user_id,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "deletion_request_status_changed",
                "governance_deletion_request",
                request_id,
                ACTOR_PROCESSOR,
                json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            ),
        )

    def _anonymized_user_id(self, user_id: str) -> str:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]
        return f"anon-{digest}"


def _parse_utc_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)