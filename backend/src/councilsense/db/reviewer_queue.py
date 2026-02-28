from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Literal


ReviewerQueueStatus = Literal["open", "in_progress", "resolved"]
ReviewerQueueReasonCode = Literal["low_evidence", "low_confidence", "policy_rule"]
ReviewerOutcomeCode = Literal[
    "confirmed_issue",
    "false_positive",
    "requires_reprocess",
    "policy_adjustment_recommended",
]
ReviewerRecommendedAction = Literal["none", "rerun_pipeline", "escalate_calibration", "open_bug"]
ReviewerQueueEventType = Literal["enqueued", "status_transition", "outcome_captured"]

ALLOWED_REASON_CODES: tuple[ReviewerQueueReasonCode, ...] = (
    "low_evidence",
    "low_confidence",
    "policy_rule",
)
ALLOWED_OUTCOME_CODES: tuple[ReviewerOutcomeCode, ...] = (
    "confirmed_issue",
    "false_positive",
    "requires_reprocess",
    "policy_adjustment_recommended",
)
ALLOWED_RECOMMENDED_ACTIONS: tuple[ReviewerRecommendedAction, ...] = (
    "none",
    "rerun_pipeline",
    "escalate_calibration",
    "open_bug",
)


@dataclass(frozen=True)
class ReviewerQueueItemRecord:
    id: str
    audit_run_id: str
    audit_week_start_utc: str
    publication_id: str
    meeting_id: str
    city_id: str
    source_id: str | None
    processing_run_id: str | None
    status: ReviewerQueueStatus
    reason_codes: tuple[str, ...]
    claim_count: int
    claims_with_evidence_count: int
    publication_status: str
    confidence_label: str
    queued_at: str
    first_in_progress_at: str | None
    resolved_at: str | None
    last_status_changed_at: str
    outcome_code: str | None
    recommended_action: str | None
    outcome_notes: str | None
    last_reviewed_by: str | None
    last_reviewed_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReviewerQueueEventRecord:
    id: str
    queue_item_id: str
    event_type: ReviewerQueueEventType
    reason_codes: tuple[str, ...]
    from_status: str | None
    to_status: str | None
    outcome_code: str | None
    recommended_action: str | None
    actor_user_id: str | None
    notes: str | None
    created_at: str


class ReviewerQueueRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_queue_item_if_absent(
        self,
        *,
        queue_item_id: str,
        audit_run_id: str,
        audit_week_start_utc: str,
        publication_id: str,
        meeting_id: str,
        city_id: str,
        source_id: str | None,
        processing_run_id: str | None,
        reason_codes: tuple[str, ...],
        claim_count: int,
        claims_with_evidence_count: int,
        publication_status: str,
        confidence_label: str,
        queued_at: str,
    ) -> tuple[ReviewerQueueItemRecord, bool]:
        normalized_reason_codes = _normalize_reason_codes(reason_codes)
        if claim_count < 0:
            raise ValueError("claim_count must be >= 0")
        if claims_with_evidence_count < 0 or claims_with_evidence_count > claim_count:
            raise ValueError("claims_with_evidence_count must be in [0, claim_count]")

        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO reviewer_queue_items (
                    id,
                    audit_run_id,
                    audit_week_start_utc,
                    publication_id,
                    meeting_id,
                    city_id,
                    source_id,
                    processing_run_id,
                    status,
                    reason_codes_json,
                    claim_count,
                    claims_with_evidence_count,
                    publication_status,
                    confidence_label,
                    queued_at,
                    last_status_changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    queue_item_id,
                    audit_run_id,
                    audit_week_start_utc,
                    publication_id,
                    meeting_id,
                    city_id,
                    source_id,
                    processing_run_id,
                    _encode_json_array(normalized_reason_codes),
                    claim_count,
                    claims_with_evidence_count,
                    publication_status,
                    confidence_label,
                    queued_at,
                    queued_at,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                audit_run_id,
                audit_week_start_utc,
                publication_id,
                meeting_id,
                city_id,
                source_id,
                processing_run_id,
                status,
                reason_codes_json,
                claim_count,
                claims_with_evidence_count,
                publication_status,
                confidence_label,
                queued_at,
                first_in_progress_at,
                resolved_at,
                last_status_changed_at,
                outcome_code,
                recommended_action,
                outcome_notes,
                last_reviewed_by,
                last_reviewed_at,
                created_at,
                updated_at
            FROM reviewer_queue_items
            WHERE audit_run_id = ? AND publication_id = ?
            """,
            (audit_run_id, publication_id),
        ).fetchone()
        assert row is not None
        return (_to_queue_item_record(row), cursor.rowcount == 1)

    def get_queue_item(self, *, queue_item_id: str) -> ReviewerQueueItemRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                audit_run_id,
                audit_week_start_utc,
                publication_id,
                meeting_id,
                city_id,
                source_id,
                processing_run_id,
                status,
                reason_codes_json,
                claim_count,
                claims_with_evidence_count,
                publication_status,
                confidence_label,
                queued_at,
                first_in_progress_at,
                resolved_at,
                last_status_changed_at,
                outcome_code,
                recommended_action,
                outcome_notes,
                last_reviewed_by,
                last_reviewed_at,
                created_at,
                updated_at
            FROM reviewer_queue_items
            WHERE id = ?
            """,
            (queue_item_id,),
        ).fetchone()
        if row is None:
            return None
        return _to_queue_item_record(row)

    def list_queue_items(
        self,
        *,
        statuses: tuple[ReviewerQueueStatus, ...] = ("open", "in_progress"),
        limit: int = 100,
    ) -> tuple[ReviewerQueueItemRecord, ...]:
        normalized_limit = max(1, limit)
        if not statuses:
            return ()

        placeholders = ",".join("?" for _ in statuses)
        rows = self._connection.execute(
            f"""
            SELECT
                id,
                audit_run_id,
                audit_week_start_utc,
                publication_id,
                meeting_id,
                city_id,
                source_id,
                processing_run_id,
                status,
                reason_codes_json,
                claim_count,
                claims_with_evidence_count,
                publication_status,
                confidence_label,
                queued_at,
                first_in_progress_at,
                resolved_at,
                last_status_changed_at,
                outcome_code,
                recommended_action,
                outcome_notes,
                last_reviewed_by,
                last_reviewed_at,
                created_at,
                updated_at
            FROM reviewer_queue_items
            WHERE status IN ({placeholders})
            ORDER BY queued_at ASC, id ASC
            LIMIT ?
            """,
            (*statuses, normalized_limit),
        ).fetchall()
        return tuple(_to_queue_item_record(row) for row in rows)

    def mark_in_progress(
        self,
        *,
        queue_item_id: str,
        reviewer_user_id: str,
        changed_at: str,
    ) -> ReviewerQueueItemRecord | None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE reviewer_queue_items
                SET
                    status = 'in_progress',
                    first_in_progress_at = COALESCE(first_in_progress_at, ?),
                    last_status_changed_at = ?,
                    last_reviewed_by = ?,
                    last_reviewed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'open'
                """,
                (changed_at, changed_at, reviewer_user_id, changed_at, queue_item_id),
            )
        return self.get_queue_item(queue_item_id=queue_item_id)

    def resolve_with_outcome(
        self,
        *,
        queue_item_id: str,
        reviewer_user_id: str,
        resolved_at: str,
        outcome_code: str,
        recommended_action: str,
        outcome_notes: str | None,
    ) -> ReviewerQueueItemRecord | None:
        if outcome_code not in ALLOWED_OUTCOME_CODES:
            supported = ", ".join(ALLOWED_OUTCOME_CODES)
            raise ValueError(f"outcome_code must be one of: {supported}")
        if recommended_action not in ALLOWED_RECOMMENDED_ACTIONS:
            supported = ", ".join(ALLOWED_RECOMMENDED_ACTIONS)
            raise ValueError(f"recommended_action must be one of: {supported}")

        with self._connection:
            self._connection.execute(
                """
                UPDATE reviewer_queue_items
                SET
                    status = 'resolved',
                    resolved_at = ?,
                    last_status_changed_at = ?,
                    outcome_code = ?,
                    recommended_action = ?,
                    outcome_notes = ?,
                    last_reviewed_by = ?,
                    last_reviewed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status IN ('open', 'in_progress')
                """,
                (
                    resolved_at,
                    resolved_at,
                    outcome_code,
                    recommended_action,
                    outcome_notes,
                    reviewer_user_id,
                    resolved_at,
                    queue_item_id,
                ),
            )
        return self.get_queue_item(queue_item_id=queue_item_id)

    def append_event(
        self,
        *,
        event_id: str,
        queue_item_id: str,
        event_type: ReviewerQueueEventType,
        reason_codes: tuple[str, ...] = (),
        from_status: str | None = None,
        to_status: str | None = None,
        outcome_code: str | None = None,
        recommended_action: str | None = None,
        actor_user_id: str | None = None,
        notes: str | None = None,
        created_at: str | None = None,
    ) -> ReviewerQueueEventRecord:
        normalized_reason_codes = _normalize_reason_codes(reason_codes, allow_empty=True)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO reviewer_queue_events (
                    id,
                    queue_item_id,
                    event_type,
                    reason_codes_json,
                    from_status,
                    to_status,
                    outcome_code,
                    recommended_action,
                    actor_user_id,
                    notes,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (
                    event_id,
                    queue_item_id,
                    event_type,
                    _encode_json_array(normalized_reason_codes) if normalized_reason_codes else None,
                    from_status,
                    to_status,
                    outcome_code,
                    recommended_action,
                    actor_user_id,
                    notes,
                    created_at,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                queue_item_id,
                event_type,
                reason_codes_json,
                from_status,
                to_status,
                outcome_code,
                recommended_action,
                actor_user_id,
                notes,
                created_at
            FROM reviewer_queue_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        assert row is not None
        return _to_event_record(row)

    def list_events_for_item(self, *, queue_item_id: str) -> tuple[ReviewerQueueEventRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                queue_item_id,
                event_type,
                reason_codes_json,
                from_status,
                to_status,
                outcome_code,
                recommended_action,
                actor_user_id,
                notes,
                created_at
            FROM reviewer_queue_events
            WHERE queue_item_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (queue_item_id,),
        ).fetchall()
        return tuple(_to_event_record(row) for row in rows)


def _normalize_reason_codes(reason_codes: tuple[str, ...], *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({code.strip() for code in reason_codes if code.strip()}))
    if not allow_empty and not normalized:
        raise ValueError("reason_codes must contain at least one code")
    for code in normalized:
        if code not in ALLOWED_REASON_CODES:
            supported = ", ".join(ALLOWED_REASON_CODES)
            raise ValueError(f"reason_codes contains unsupported code '{code}', expected one of: {supported}")
    return normalized


def _encode_json_array(items: tuple[str, ...]) -> str:
    return json.dumps(list(items), separators=(",", ":"), sort_keys=False)


def _decode_json_array(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, list):
        return ()
    values: list[str] = []
    for item in payload:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
    return tuple(values)


def _to_queue_item_record(row: sqlite3.Row | tuple[object, ...]) -> ReviewerQueueItemRecord:
    return ReviewerQueueItemRecord(
        id=str(row[0]),
        audit_run_id=str(row[1]),
        audit_week_start_utc=str(row[2]),
        publication_id=str(row[3]),
        meeting_id=str(row[4]),
        city_id=str(row[5]),
        source_id=str(row[6]) if row[6] is not None else None,
        processing_run_id=str(row[7]) if row[7] is not None else None,
        status=str(row[8]),
        reason_codes=_decode_json_array(str(row[9]) if row[9] is not None else None),
        claim_count=int(row[10]),
        claims_with_evidence_count=int(row[11]),
        publication_status=str(row[12]),
        confidence_label=str(row[13]),
        queued_at=str(row[14]),
        first_in_progress_at=str(row[15]) if row[15] is not None else None,
        resolved_at=str(row[16]) if row[16] is not None else None,
        last_status_changed_at=str(row[17]),
        outcome_code=str(row[18]) if row[18] is not None else None,
        recommended_action=str(row[19]) if row[19] is not None else None,
        outcome_notes=str(row[20]) if row[20] is not None else None,
        last_reviewed_by=str(row[21]) if row[21] is not None else None,
        last_reviewed_at=str(row[22]) if row[22] is not None else None,
        created_at=str(row[23]),
        updated_at=str(row[24]),
    )


def _to_event_record(row: sqlite3.Row | tuple[object, ...]) -> ReviewerQueueEventRecord:
    return ReviewerQueueEventRecord(
        id=str(row[0]),
        queue_item_id=str(row[1]),
        event_type=str(row[2]),
        reason_codes=_decode_json_array(str(row[3]) if row[3] is not None else None),
        from_status=str(row[4]) if row[4] is not None else None,
        to_status=str(row[5]) if row[5] is not None else None,
        outcome_code=str(row[6]) if row[6] is not None else None,
        recommended_action=str(row[7]) if row[7] is not None else None,
        actor_user_id=str(row[8]) if row[8] is not None else None,
        notes=str(row[9]) if row[9] is not None else None,
        created_at=str(row[10]),
    )
