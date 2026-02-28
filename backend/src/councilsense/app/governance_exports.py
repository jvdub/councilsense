from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import sqlite3
from typing import Any, Protocol
from uuid import uuid4


class UserProfileReader(Protocol):
    def get_profile(self, user_id: str) -> Any: ...


EXPORT_SCHEMA_VERSION = "2026-02-28"
ACTOR_PROCESSOR = "system:governance-export-processor"


class GovernanceExportNotFoundError(Exception):
    pass


class GovernanceExportOwnershipError(Exception):
    pass


class GovernanceExportArtifactUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class GovernanceExportRequestView:
    id: str
    user_id: str
    idempotency_key: str
    status: str
    scope: dict[str, bool]
    artifact_uri: str | None
    error_code: str | None
    completed_at: str | None
    processing_attempt_count: int
    max_processing_attempts: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GovernanceExportArtifactView:
    artifact_uri: str
    schema_version: str
    generated_at: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class GovernanceExportProcessingResult:
    claimed_count: int
    completed_count: int
    failed_count: int
    terminal_count: int


class GovernanceExportService:
    def __init__(self, *, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_request(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        requested_by: str,
        scope: dict[str, bool] | None = None,
    ) -> GovernanceExportRequestView:
        normalized_scope = self._normalize_scope(scope)
        self._ensure_governance_identity(user_id)

        request_id = f"exp-{uuid4().hex}"
        scope_json = json.dumps(normalized_scope, separators=(",", ":"), sort_keys=True)

        try:
            self._connection.execute(
                """
                INSERT INTO governance_export_requests (
                    id,
                    user_id,
                    idempotency_key,
                    status,
                    requested_by,
                    scope_json
                )
                VALUES (?, ?, ?, 'requested', ?, ?)
                """,
                (request_id, user_id, idempotency_key, requested_by, scope_json),
            )
        except sqlite3.IntegrityError:
            row = self._connection.execute(
                """
                SELECT id, user_id
                FROM governance_export_requests
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise
            existing_request_id, existing_user_id = str(row[0]), str(row[1])
            if existing_user_id != user_id:
                raise GovernanceExportOwnershipError
            return self.get_request(user_id=user_id, request_id=existing_request_id)

        return self.get_request(user_id=user_id, request_id=request_id)

    def get_request(self, *, user_id: str, request_id: str) -> GovernanceExportRequestView:
        row = self._connection.execute(
            """
            SELECT
                id,
                user_id,
                idempotency_key,
                status,
                scope_json,
                artifact_uri,
                error_code,
                completed_at,
                processing_attempt_count,
                max_processing_attempts,
                created_at,
                updated_at
            FROM governance_export_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise GovernanceExportNotFoundError

        request_user_id = str(row[1])
        if request_user_id != user_id:
            raise GovernanceExportOwnershipError

        return GovernanceExportRequestView(
            id=str(row[0]),
            user_id=request_user_id,
            idempotency_key=str(row[2]),
            status=str(row[3]),
            scope=self._parse_scope_json(str(row[4])),
            artifact_uri=str(row[5]) if row[5] is not None else None,
            error_code=str(row[6]) if row[6] is not None else None,
            completed_at=str(row[7]) if row[7] is not None else None,
            processing_attempt_count=int(row[8]),
            max_processing_attempts=int(row[9]),
            created_at=str(row[10]),
            updated_at=str(row[11]),
        )

    def get_artifact(self, *, user_id: str, request_id: str) -> GovernanceExportArtifactView:
        row = self._connection.execute(
            """
            SELECT
                req.user_id,
                req.artifact_uri,
                art.schema_version,
                art.generated_at,
                art.content_json
            FROM governance_export_requests req
            JOIN governance_export_artifacts art ON art.request_id = req.id
            WHERE req.id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            request = self.get_request(user_id=user_id, request_id=request_id)
            if request.status != "completed" or request.artifact_uri is None:
                raise GovernanceExportArtifactUnavailableError
            raise GovernanceExportNotFoundError

        request_user_id = str(row[0])
        if request_user_id != user_id:
            raise GovernanceExportOwnershipError

        return GovernanceExportArtifactView(
            artifact_uri=str(row[1]),
            schema_version=str(row[2]),
            generated_at=str(row[3]),
            payload=json.loads(str(row[4])),
        )

    def _ensure_governance_identity(self, user_id: str) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO governance_user_identities (user_id)
            VALUES (?)
            """,
            (user_id,),
        )

    def _normalize_scope(self, scope: dict[str, bool] | None) -> dict[str, bool]:
        defaults = {
            "include_profile": True,
            "include_preferences": True,
            "include_notification_history": True,
        }
        if scope is None:
            return defaults

        merged = dict(defaults)
        for key in defaults:
            if key in scope:
                merged[key] = bool(scope[key])
        return merged

    def _parse_scope_json(self, scope_json: str) -> dict[str, bool]:
        try:
            loaded = json.loads(scope_json)
            if not isinstance(loaded, dict):
                return self._normalize_scope(None)
            return self._normalize_scope({key: bool(value) for key, value in loaded.items()})
        except (ValueError, TypeError):
            return self._normalize_scope(None)


class GovernanceExportProcessor:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        profile_service: UserProfileReader,
    ) -> None:
        self._connection = connection
        self._profile_service = profile_service

    def run_once(self, *, batch_size: int = 25) -> GovernanceExportProcessingResult:
        pending_rows = self._connection.execute(
            """
            SELECT id, user_id, status, requested_by, scope_json, processing_attempt_count, max_processing_attempts
            FROM governance_export_requests
            WHERE status IN ('requested', 'failed')
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()

        claimed_count = len(pending_rows)
        completed_count = 0
        failed_count = 0
        terminal_count = 0

        for row in pending_rows:
            request_id = str(row[0])
            user_id = str(row[1])
            current_status = str(row[2])
            requested_by = str(row[3])
            scope = self._parse_scope(str(row[4]))
            attempt_count = int(row[5])
            max_attempts = int(row[6])

            if current_status == "requested":
                self._connection.execute(
                    """
                    UPDATE governance_export_requests
                    SET status = 'accepted', requested_by = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (ACTOR_PROCESSOR, request_id),
                )

            self._connection.execute(
                """
                UPDATE governance_export_requests
                SET status = 'processing', requested_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ACTOR_PROCESSOR, request_id),
            )

            try:
                artifact = self._build_artifact(user_id=user_id, scope=scope)
            except Exception:
                next_attempt_count = attempt_count + 1
                if next_attempt_count >= max_attempts:
                    self._connection.execute(
                        """
                        UPDATE governance_export_requests
                        SET
                            status = 'cancelled',
                            requested_by = ?,
                            error_code = 'export_generation_failed_terminal',
                            processing_attempt_count = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (ACTOR_PROCESSOR, next_attempt_count, request_id),
                    )
                    terminal_count += 1
                    continue

                self._connection.execute(
                    """
                    UPDATE governance_export_requests
                    SET
                        status = 'failed',
                        requested_by = ?,
                        error_code = 'export_generation_failed_retryable',
                        processing_attempt_count = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (ACTOR_PROCESSOR, next_attempt_count, request_id),
                )
                failed_count += 1
                continue

            artifact_id = f"artifact-{uuid4().hex}"
            artifact_uri = f"governance-export://{request_id}"
            generated_at = artifact["generated_at"]
            payload_json = json.dumps(artifact, separators=(",", ":"), sort_keys=True)

            self._connection.execute(
                """
                INSERT INTO governance_export_artifacts (
                    id,
                    request_id,
                    user_id,
                    schema_version,
                    generated_at,
                    content_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    generated_at = excluded.generated_at,
                    content_json = excluded.content_json
                """,
                (artifact_id, request_id, user_id, EXPORT_SCHEMA_VERSION, generated_at, payload_json),
            )

            self._connection.execute(
                """
                UPDATE governance_export_requests
                SET
                    status = 'completed',
                    requested_by = ?,
                    artifact_uri = ?,
                    error_code = NULL,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ACTOR_PROCESSOR, artifact_uri, request_id),
            )
            completed_count += 1

        return GovernanceExportProcessingResult(
            claimed_count=claimed_count,
            completed_count=completed_count,
            failed_count=failed_count,
            terminal_count=terminal_count,
        )

    def _build_artifact(self, *, user_id: str, scope: dict[str, bool]) -> dict[str, Any]:
        generated_at = datetime.now(tz=UTC).isoformat()
        profile = self._profile_service.get_profile(user_id)

        profile_section = {
            "provenance": {
                "source": "profile_service",
                "retrieved_at": generated_at,
                "redaction_policy": "allowlist-v1",
            },
            "data": {
                "user_id": profile.user_id,
                "home_city_id": profile.home_city_id,
            },
        }
        preferences_section = {
            "provenance": {
                "source": "profile_service",
                "retrieved_at": generated_at,
                "redaction_policy": "allowlist-v1",
            },
            "data": {
                "notifications_enabled": profile.notifications_enabled,
                "notifications_paused_until": (
                    profile.notifications_paused_until.isoformat()
                    if profile.notifications_paused_until is not None
                    else None
                ),
            },
        }

        notification_rows = self._connection.execute(
            """
            SELECT
                outbox.id,
                outbox.meeting_id,
                outbox.city_id,
                outbox.notification_type,
                outbox.status,
                outbox.attempt_count,
                outbox.max_attempts,
                outbox.subscription_id,
                outbox.created_at,
                outbox.last_attempt_at,
                outbox.sent_at
            FROM notification_outbox outbox
            WHERE outbox.user_id = ?
            ORDER BY outbox.created_at ASC, outbox.id ASC
            """,
            (user_id,),
        ).fetchall()

        history_items: list[dict[str, Any]] = []
        for row in notification_rows:
            outbox_id = str(row[0])
            attempts = self._connection.execute(
                """
                SELECT attempt_number, outcome, attempted_at
                FROM notification_delivery_attempts
                WHERE outbox_id = ?
                ORDER BY attempt_number ASC
                """,
                (outbox_id,),
            ).fetchall()

            history_items.append(
                {
                    "notification_id": outbox_id,
                    "meeting_id": str(row[1]),
                    "city_id": str(row[2]),
                    "notification_type": str(row[3]),
                    "status": str(row[4]),
                    "attempt_count": int(row[5]),
                    "max_attempts": int(row[6]),
                    "subscription_id": str(row[7]) if row[7] is not None else None,
                    "created_at": str(row[8]),
                    "last_attempt_at": str(row[9]) if row[9] is not None else None,
                    "sent_at": str(row[10]) if row[10] is not None else None,
                    "attempts": [
                        {
                            "attempt_number": int(attempt[0]),
                            "outcome": str(attempt[1]),
                            "attempted_at": str(attempt[2]),
                        }
                        for attempt in attempts
                    ],
                }
            )

        notification_history_section = {
            "provenance": {
                "source": "notification_outbox_and_attempts",
                "retrieved_at": generated_at,
                "redaction_policy": "allowlist-v1",
            },
            "data": history_items,
        }

        sections: dict[str, Any] = {}
        if scope.get("include_profile", True):
            sections["profile"] = profile_section
        if scope.get("include_preferences", True):
            sections["preferences"] = preferences_section
        if scope.get("include_notification_history", True):
            sections["notification_history"] = notification_history_section

        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "generated_at": generated_at,
            "sections": sections,
            "metadata": {
                "export_type": "user_data_export",
                "redaction_profile": "gov-013-allowlist-v1",
            },
        }

    def _parse_scope(self, scope_json: str) -> dict[str, bool]:
        try:
            loaded = json.loads(scope_json)
            if not isinstance(loaded, dict):
                return {
                    "include_profile": True,
                    "include_preferences": True,
                    "include_notification_history": True,
                }
            return {
                "include_profile": bool(loaded.get("include_profile", True)),
                "include_preferences": bool(loaded.get("include_preferences", True)),
                "include_notification_history": bool(loaded.get("include_notification_history", True)),
            }
        except (ValueError, TypeError):
            return {
                "include_profile": True,
                "include_preferences": True,
                "include_notification_history": True,
            }
