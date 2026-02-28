from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Callable
from uuid import uuid4

from councilsense.db.reviewer_queue import (
    ALLOWED_OUTCOME_CODES,
    ALLOWED_RECOMMENDED_ACTIONS,
    ReviewerQueueEventRecord,
    ReviewerQueueItemRecord,
    ReviewerQueueRepository,
    ReviewerRecommendedAction,
)


REVIEWER_ALLOWED_ROLES = frozenset(("ops-quality-reviewer", "ops-quality-oncall"))


class ReviewerQueueAuthorizationError(PermissionError):
    pass


class ReviewerQueueNotFoundError(LookupError):
    pass


class ReviewerQueueStateError(RuntimeError):
    pass


class ReviewerQueueService:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        repository: ReviewerQueueRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._repository = repository or ReviewerQueueRepository(connection)
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def seed_from_ecr_audit_run(self, *, run_id: str) -> tuple[ReviewerQueueItemRecord, ...]:
        report_row = self._connection.execute(
            """
            SELECT audit_week_start_utc, content_json
            FROM ecr_audit_report_artifacts
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if report_row is None:
            return ()

        audit_week_start_utc = str(report_row[0])
        try:
            content = json.loads(str(report_row[1]))
        except (TypeError, ValueError):
            return ()
        if not isinstance(content, dict):
            return ()

        selected_publication_ids_raw = content.get("selected_publication_ids")
        if not isinstance(selected_publication_ids_raw, list):
            return ()
        selected_publication_ids = tuple(
            item.strip()
            for item in selected_publication_ids_raw
            if isinstance(item, str) and item.strip()
        )
        if not selected_publication_ids:
            return ()

        context_rows = self._load_publication_review_context(selected_publication_ids)
        if not context_rows:
            return ()

        enqueued: list[ReviewerQueueItemRecord] = []
        queued_at = _now_iso_utc(self._now_provider())
        with self._connection:
            for row in context_rows:
                reason_codes = _derive_reason_codes(
                    publication_status=row["publication_status"],
                    confidence_label=row["confidence_label"],
                    claim_count=row["claim_count"],
                    claims_with_evidence_count=row["claims_with_evidence_count"],
                    run_status=row["run_status"],
                )
                if not reason_codes:
                    continue

                queue_item, inserted = self._repository.create_queue_item_if_absent(
                    queue_item_id=f"rq-{uuid4().hex}",
                    audit_run_id=run_id,
                    audit_week_start_utc=audit_week_start_utc,
                    publication_id=row["publication_id"],
                    meeting_id=row["meeting_id"],
                    city_id=row["city_id"],
                    source_id=row["source_id"],
                    processing_run_id=row["processing_run_id"],
                    reason_codes=reason_codes,
                    claim_count=row["claim_count"],
                    claims_with_evidence_count=row["claims_with_evidence_count"],
                    publication_status=row["publication_status"],
                    confidence_label=row["confidence_label"],
                    queued_at=queued_at,
                )
                if not inserted:
                    continue

                self._repository.append_event(
                    event_id=f"rqevt-{uuid4().hex}",
                    queue_item_id=queue_item.id,
                    event_type="enqueued",
                    reason_codes=reason_codes,
                    to_status="open",
                    created_at=queued_at,
                )
                enqueued.append(queue_item)

        return tuple(enqueued)

    def list_queue(self, *, statuses: tuple[str, ...] = ("open", "in_progress"), limit: int = 100) -> tuple[ReviewerQueueItemRecord, ...]:
        return self._repository.list_queue_items(statuses=statuses, limit=limit)

    def start_review(
        self,
        *,
        queue_item_id: str,
        reviewer_user_id: str,
        reviewer_roles: tuple[str, ...],
    ) -> ReviewerQueueItemRecord:
        self._require_reviewer_role(reviewer_roles)

        existing = self._repository.get_queue_item(queue_item_id=queue_item_id)
        if existing is None:
            raise ReviewerQueueNotFoundError(f"queue item not found: {queue_item_id}")
        if existing.status == "resolved":
            raise ReviewerQueueStateError("queue item is already resolved")
        if existing.status == "in_progress":
            return existing

        changed_at = _now_iso_utc(self._now_provider())
        updated = self._repository.mark_in_progress(
            queue_item_id=queue_item_id,
            reviewer_user_id=reviewer_user_id,
            changed_at=changed_at,
        )
        assert updated is not None
        self._repository.append_event(
            event_id=f"rqevt-{uuid4().hex}",
            queue_item_id=queue_item_id,
            event_type="status_transition",
            from_status="open",
            to_status="in_progress",
            actor_user_id=reviewer_user_id,
            created_at=changed_at,
        )
        return updated

    def record_outcome(
        self,
        *,
        queue_item_id: str,
        reviewer_user_id: str,
        reviewer_roles: tuple[str, ...],
        outcome_code: str,
        recommended_action: ReviewerRecommendedAction,
        outcome_notes: str | None,
    ) -> ReviewerQueueItemRecord:
        self._require_reviewer_role(reviewer_roles)

        if outcome_code not in ALLOWED_OUTCOME_CODES:
            supported = ", ".join(ALLOWED_OUTCOME_CODES)
            raise ValueError(f"outcome_code must be one of: {supported}")
        if recommended_action not in ALLOWED_RECOMMENDED_ACTIONS:
            supported = ", ".join(ALLOWED_RECOMMENDED_ACTIONS)
            raise ValueError(f"recommended_action must be one of: {supported}")

        existing = self._repository.get_queue_item(queue_item_id=queue_item_id)
        if existing is None:
            raise ReviewerQueueNotFoundError(f"queue item not found: {queue_item_id}")
        if existing.status == "resolved":
            raise ReviewerQueueStateError("queue item is already resolved")

        resolved_at = _now_iso_utc(self._now_provider())
        updated = self._repository.resolve_with_outcome(
            queue_item_id=queue_item_id,
            reviewer_user_id=reviewer_user_id,
            resolved_at=resolved_at,
            outcome_code=outcome_code,
            recommended_action=recommended_action,
            outcome_notes=outcome_notes,
        )
        if updated is None:
            raise ReviewerQueueNotFoundError(f"queue item not found: {queue_item_id}")

        from_status = "in_progress" if existing.status == "in_progress" else "open"
        self._repository.append_event(
            event_id=f"rqevt-{uuid4().hex}",
            queue_item_id=queue_item_id,
            event_type="outcome_captured",
            outcome_code=outcome_code,
            recommended_action=recommended_action,
            actor_user_id=reviewer_user_id,
            notes=outcome_notes,
            created_at=resolved_at,
        )
        self._repository.append_event(
            event_id=f"rqevt-{uuid4().hex}",
            queue_item_id=queue_item_id,
            event_type="status_transition",
            from_status=from_status,
            to_status="resolved",
            outcome_code=outcome_code,
            recommended_action=recommended_action,
            actor_user_id=reviewer_user_id,
            notes=outcome_notes,
            created_at=resolved_at,
        )
        return updated

    def export_review_history(self, *, queue_item_id: str) -> tuple[ReviewerQueueEventRecord, ...]:
        return self._repository.list_events_for_item(queue_item_id=queue_item_id)

    def _require_reviewer_role(self, roles: tuple[str, ...]) -> None:
        normalized = {role.strip() for role in roles if role.strip()}
        if normalized.intersection(REVIEWER_ALLOWED_ROLES):
            return
        raise ReviewerQueueAuthorizationError("reviewer role required")

    def _load_publication_review_context(
        self,
        publication_ids: tuple[str, ...],
    ) -> tuple[dict[str, str | int | None], ...]:
        placeholders = ",".join("?" for _ in publication_ids)
        rows = self._connection.execute(
            f"""
            SELECT
                sp.id,
                sp.meeting_id,
                m.city_id,
                sp.processing_run_id,
                sp.publication_status,
                sp.confidence_label,
                pso.metadata_json,
                pr.status,
                COUNT(pc.id) AS claim_count,
                COUNT(DISTINCT CASE WHEN cep.id IS NOT NULL THEN pc.id END) AS claims_with_evidence_count
            FROM summary_publications sp
            JOIN meetings m ON m.id = sp.meeting_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = sp.publish_stage_outcome_id
            LEFT JOIN processing_runs pr ON pr.id = sp.processing_run_id
            LEFT JOIN publication_claims pc ON pc.publication_id = sp.id
            LEFT JOIN claim_evidence_pointers cep ON cep.claim_id = pc.id
            WHERE sp.id IN ({placeholders})
            GROUP BY
                sp.id,
                sp.meeting_id,
                m.city_id,
                sp.processing_run_id,
                sp.publication_status,
                sp.confidence_label,
                pso.metadata_json,
                pr.status
            ORDER BY sp.published_at ASC, sp.id ASC
            """,
            publication_ids,
        ).fetchall()

        context: list[dict[str, str | int | None]] = []
        for row in rows:
            metadata_json = str(row[6]) if row[6] is not None else None
            context.append(
                {
                    "publication_id": str(row[0]),
                    "meeting_id": str(row[1]),
                    "city_id": str(row[2]),
                    "processing_run_id": str(row[3]) if row[3] is not None else None,
                    "publication_status": str(row[4]),
                    "confidence_label": str(row[5]),
                    "source_id": _extract_source_id_from_metadata(metadata_json),
                    "run_status": str(row[7]) if row[7] is not None else None,
                    "claim_count": int(row[8]),
                    "claims_with_evidence_count": int(row[9]),
                }
            )
        return tuple(context)


def _derive_reason_codes(
    *,
    publication_status: str,
    confidence_label: str,
    claim_count: int,
    claims_with_evidence_count: int,
    run_status: str | None,
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if publication_status == "limited_confidence" or confidence_label in {"low", "limited_confidence"}:
        reason_codes.append("low_confidence")
    if claim_count > 0 and claims_with_evidence_count < claim_count:
        reason_codes.append("low_evidence")
    if run_status == "manual_review_needed":
        reason_codes.append("policy_rule")
    return tuple(sorted(set(reason_codes)))


def _extract_source_id_from_metadata(metadata_json: str | None) -> str | None:
    if metadata_json is None:
        return None

    try:
        metadata = json.loads(metadata_json)
    except (TypeError, ValueError):
        return None

    if not isinstance(metadata, dict):
        return None

    for key in ("source_id", "city_source_id", "sourceId"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _now_iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()
