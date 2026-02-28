from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import sqlite3
from typing import Any, Callable
from uuid import uuid4


DEFAULT_ECR_TARGET = 0.85
DEFAULT_ESCALATION_OWNER_ROLE = "ops-quality-oncall"
ALLOWED_REVIEWER_OUTCOMES: tuple[str, ...] = (
    "confirmed_issue",
    "false_positive",
    "requires_reprocess",
    "policy_adjustment_recommended",
)


@dataclass(frozen=True)
class QualityOpsWeeklyReport:
    audit_week_start_utc: str
    audit_week_end_utc: str
    generated_at_utc: str
    source_report_artifact_uri: str
    ecr: float
    ecr_target: float
    target_attained: bool
    target_status: str
    low_confidence_labeling_rate: float
    reviewer_queue_item_count: int
    reviewer_queue_resolved_count: int
    reviewer_queue_closure_rate: float
    reviewer_backlog_open_count: int
    reviewer_backlog_in_progress_count: int
    reviewer_outcome_counts: dict[str, int]
    calibration_policy_version: str | None
    escalation_owner_role: str | None
    escalation_triggered_at_utc: str | None


class QualityOpsDashboardService:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def upsert_weekly_report(
        self,
        *,
        audit_week_start_utc: datetime,
        ecr_target: float = DEFAULT_ECR_TARGET,
        escalation_owner_role: str = DEFAULT_ESCALATION_OWNER_ROLE,
    ) -> QualityOpsWeeklyReport:
        if not 0.0 <= ecr_target <= 1.0:
            raise ValueError("ecr_target must be within [0.0, 1.0]")

        normalized_week_start = _normalize_utc_datetime(audit_week_start_utc).isoformat()
        generated_at_utc = _normalize_utc_datetime(self._now_provider()).isoformat()
        report = self._build_weekly_report(
            audit_week_start_utc=normalized_week_start,
            generated_at_utc=generated_at_utc,
            ecr_target=ecr_target,
            escalation_owner_role=escalation_owner_role,
        )

        summary_payload = {
            "report_version": "st-015-quality-ops-weekly-report-v1",
            "audit_week_start_utc": report.audit_week_start_utc,
            "audit_week_end_utc": report.audit_week_end_utc,
            "generated_at_utc": report.generated_at_utc,
            "source_report_artifact_uri": report.source_report_artifact_uri,
            "target": {
                "ecr_target": report.ecr_target,
                "ecr_actual": report.ecr,
                "target_attained": report.target_attained,
                "target_status": report.target_status,
            },
            "metrics": {
                "low_confidence_labeling_rate": report.low_confidence_labeling_rate,
                "reviewer_queue_item_count": report.reviewer_queue_item_count,
                "reviewer_queue_resolved_count": report.reviewer_queue_resolved_count,
                "reviewer_queue_closure_rate": report.reviewer_queue_closure_rate,
                "reviewer_backlog_open_count": report.reviewer_backlog_open_count,
                "reviewer_backlog_in_progress_count": report.reviewer_backlog_in_progress_count,
                "reviewer_outcome_counts": report.reviewer_outcome_counts,
            },
            "calibration_policy_version": report.calibration_policy_version,
            "escalation": {
                "owner_role": report.escalation_owner_role,
                "triggered_at_utc": report.escalation_triggered_at_utc,
            },
        }

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO quality_ops_weekly_reports (
                    id,
                    audit_week_start_utc,
                    audit_week_end_utc,
                    generated_at_utc,
                    source_report_artifact_uri,
                    ecr,
                    ecr_target,
                    target_attained,
                    target_status,
                    low_confidence_labeling_rate,
                    reviewer_queue_item_count,
                    reviewer_queue_resolved_count,
                    reviewer_queue_closure_rate,
                    reviewer_backlog_open_count,
                    reviewer_backlog_in_progress_count,
                    reviewer_outcome_counts_json,
                    calibration_policy_version,
                    escalation_owner_role,
                    escalation_triggered_at_utc,
                    summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(audit_week_start_utc) DO UPDATE SET
                    audit_week_end_utc = excluded.audit_week_end_utc,
                    generated_at_utc = excluded.generated_at_utc,
                    source_report_artifact_uri = excluded.source_report_artifact_uri,
                    ecr = excluded.ecr,
                    ecr_target = excluded.ecr_target,
                    target_attained = excluded.target_attained,
                    target_status = excluded.target_status,
                    low_confidence_labeling_rate = excluded.low_confidence_labeling_rate,
                    reviewer_queue_item_count = excluded.reviewer_queue_item_count,
                    reviewer_queue_resolved_count = excluded.reviewer_queue_resolved_count,
                    reviewer_queue_closure_rate = excluded.reviewer_queue_closure_rate,
                    reviewer_backlog_open_count = excluded.reviewer_backlog_open_count,
                    reviewer_backlog_in_progress_count = excluded.reviewer_backlog_in_progress_count,
                    reviewer_outcome_counts_json = excluded.reviewer_outcome_counts_json,
                    calibration_policy_version = excluded.calibration_policy_version,
                    escalation_owner_role = excluded.escalation_owner_role,
                    escalation_triggered_at_utc = excluded.escalation_triggered_at_utc,
                    summary_json = excluded.summary_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    f"quality-weekly-{uuid4().hex}",
                    report.audit_week_start_utc,
                    report.audit_week_end_utc,
                    report.generated_at_utc,
                    report.source_report_artifact_uri,
                    report.ecr,
                    report.ecr_target,
                    1 if report.target_attained else 0,
                    report.target_status,
                    report.low_confidence_labeling_rate,
                    report.reviewer_queue_item_count,
                    report.reviewer_queue_resolved_count,
                    report.reviewer_queue_closure_rate,
                    report.reviewer_backlog_open_count,
                    report.reviewer_backlog_in_progress_count,
                    json.dumps(report.reviewer_outcome_counts, separators=(",", ":"), sort_keys=True),
                    report.calibration_policy_version,
                    report.escalation_owner_role,
                    report.escalation_triggered_at_utc,
                    json.dumps(summary_payload, separators=(",", ":"), sort_keys=True),
                ),
            )

        return report

    def refresh_recent_reports(
        self,
        *,
        limit: int = 12,
        ecr_target: float = DEFAULT_ECR_TARGET,
        escalation_owner_role: str = DEFAULT_ESCALATION_OWNER_ROLE,
    ) -> tuple[QualityOpsWeeklyReport, ...]:
        normalized_limit = max(1, limit)
        rows = self._connection.execute(
            """
            SELECT audit_week_start_utc
            FROM ecr_audit_report_artifacts
            ORDER BY audit_week_start_utc DESC
            LIMIT ?
            """,
            (normalized_limit,),
        ).fetchall()

        reports: list[QualityOpsWeeklyReport] = []
        for row in rows:
            week_start = datetime.fromisoformat(str(row[0]))
            reports.append(
                self.upsert_weekly_report(
                    audit_week_start_utc=week_start,
                    ecr_target=ecr_target,
                    escalation_owner_role=escalation_owner_role,
                )
            )
        return tuple(reports)

    def list_weekly_reports(self, *, limit: int = 12) -> tuple[QualityOpsWeeklyReport, ...]:
        normalized_limit = max(1, limit)
        rows = self._connection.execute(
            """
            SELECT
                audit_week_start_utc,
                audit_week_end_utc,
                generated_at_utc,
                source_report_artifact_uri,
                ecr,
                ecr_target,
                target_attained,
                target_status,
                low_confidence_labeling_rate,
                reviewer_queue_item_count,
                reviewer_queue_resolved_count,
                reviewer_queue_closure_rate,
                reviewer_backlog_open_count,
                reviewer_backlog_in_progress_count,
                reviewer_outcome_counts_json,
                calibration_policy_version,
                escalation_owner_role,
                escalation_triggered_at_utc
            FROM quality_ops_weekly_reports
            ORDER BY audit_week_start_utc DESC
            LIMIT ?
            """,
            (normalized_limit,),
        ).fetchall()
        return tuple(self._row_to_weekly_report(row) for row in rows)

    def _build_weekly_report(
        self,
        *,
        audit_week_start_utc: str,
        generated_at_utc: str,
        ecr_target: float,
        escalation_owner_role: str,
    ) -> QualityOpsWeeklyReport:
        artifact_row = self._connection.execute(
            """
            SELECT
                audit_week_start_utc,
                audit_week_end_utc,
                artifact_uri,
                ecr,
                content_json
            FROM ecr_audit_report_artifacts
            WHERE audit_week_start_utc = ?
            """,
            (audit_week_start_utc,),
        ).fetchone()
        if artifact_row is None:
            raise LookupError(f"No ECR artifact found for week: {audit_week_start_utc}")

        selected_publication_ids = _extract_selected_publication_ids(content_json=str(artifact_row[4]))
        low_confidence_labeling_rate = self._compute_low_confidence_labeling_rate(selected_publication_ids)

        queue_counts_row = self._connection.execute(
            """
            SELECT
                COUNT(*) AS queue_item_count,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS queue_resolved_count,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS backlog_open_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS backlog_in_progress_count
            FROM reviewer_queue_items
            WHERE audit_week_start_utc = ?
            """,
            (audit_week_start_utc,),
        ).fetchone()
        queue_item_count = int(queue_counts_row[0]) if queue_counts_row is not None and queue_counts_row[0] is not None else 0
        queue_resolved_count = int(queue_counts_row[1]) if queue_counts_row is not None and queue_counts_row[1] is not None else 0
        backlog_open_count = int(queue_counts_row[2]) if queue_counts_row is not None and queue_counts_row[2] is not None else 0
        backlog_in_progress_count = int(queue_counts_row[3]) if queue_counts_row is not None and queue_counts_row[3] is not None else 0
        queue_closure_rate = round((queue_resolved_count / queue_item_count), 4) if queue_item_count > 0 else 0.0

        outcome_rows = self._connection.execute(
            """
            SELECT outcome_code, COUNT(*)
            FROM reviewer_queue_items
            WHERE audit_week_start_utc = ?
              AND outcome_code IS NOT NULL
            GROUP BY outcome_code
            """,
            (audit_week_start_utc,),
        ).fetchall()
        reviewer_outcome_counts = {outcome: 0 for outcome in ALLOWED_REVIEWER_OUTCOMES}
        for outcome_row in outcome_rows:
            outcome_code = str(outcome_row[0])
            if outcome_code in reviewer_outcome_counts:
                reviewer_outcome_counts[outcome_code] = int(outcome_row[1])

        calibration_row = self._connection.execute(
            """
            SELECT version
            FROM confidence_calibration_policies
            WHERE is_active = 1
            ORDER BY activated_at DESC, version DESC
            LIMIT 1
            """,
        ).fetchone()
        calibration_policy_version = str(calibration_row[0]) if calibration_row is not None else None

        ecr = float(artifact_row[3])
        target_attained = ecr >= ecr_target
        target_status = "met" if target_attained else "below_target"
        escalation_triggered_at_utc = None if target_attained else generated_at_utc
        escalation_owner = None if target_attained else escalation_owner_role.strip()

        return QualityOpsWeeklyReport(
            audit_week_start_utc=str(artifact_row[0]),
            audit_week_end_utc=str(artifact_row[1]),
            generated_at_utc=generated_at_utc,
            source_report_artifact_uri=str(artifact_row[2]),
            ecr=round(ecr, 4),
            ecr_target=round(ecr_target, 4),
            target_attained=target_attained,
            target_status=target_status,
            low_confidence_labeling_rate=low_confidence_labeling_rate,
            reviewer_queue_item_count=queue_item_count,
            reviewer_queue_resolved_count=queue_resolved_count,
            reviewer_queue_closure_rate=queue_closure_rate,
            reviewer_backlog_open_count=backlog_open_count,
            reviewer_backlog_in_progress_count=backlog_in_progress_count,
            reviewer_outcome_counts=reviewer_outcome_counts,
            calibration_policy_version=calibration_policy_version,
            escalation_owner_role=escalation_owner,
            escalation_triggered_at_utc=escalation_triggered_at_utc,
        )

    def _compute_low_confidence_labeling_rate(self, selected_publication_ids: tuple[str, ...]) -> float:
        if not selected_publication_ids:
            return 0.0

        placeholders = ",".join("?" for _ in selected_publication_ids)
        row = self._connection.execute(
            f"""
            SELECT
                COUNT(*) AS total_count,
                SUM(
                    CASE
                        WHEN publication_status = 'limited_confidence'
                             OR confidence_label IN ('low', 'limited_confidence')
                        THEN 1
                        ELSE 0
                    END
                ) AS low_confidence_count
            FROM summary_publications
            WHERE id IN ({placeholders})
            """,
            selected_publication_ids,
        ).fetchone()

        total_count = int(row[0]) if row is not None and row[0] is not None else 0
        low_confidence_count = int(row[1]) if row is not None and row[1] is not None else 0
        if total_count == 0:
            return 0.0
        return round((low_confidence_count / total_count), 4)

    def _row_to_weekly_report(self, row: sqlite3.Row | tuple[Any, ...]) -> QualityOpsWeeklyReport:
        values = tuple(row)
        outcome_counts = _decode_counts_json(str(values[14]))
        for outcome in ALLOWED_REVIEWER_OUTCOMES:
            outcome_counts.setdefault(outcome, 0)

        return QualityOpsWeeklyReport(
            audit_week_start_utc=str(values[0]),
            audit_week_end_utc=str(values[1]),
            generated_at_utc=str(values[2]),
            source_report_artifact_uri=str(values[3]),
            ecr=float(values[4]),
            ecr_target=float(values[5]),
            target_attained=bool(values[6]),
            target_status=str(values[7]),
            low_confidence_labeling_rate=float(values[8]),
            reviewer_queue_item_count=int(values[9]),
            reviewer_queue_resolved_count=int(values[10]),
            reviewer_queue_closure_rate=float(values[11]),
            reviewer_backlog_open_count=int(values[12]),
            reviewer_backlog_in_progress_count=int(values[13]),
            reviewer_outcome_counts=outcome_counts,
            calibration_policy_version=str(values[15]) if values[15] is not None else None,
            escalation_owner_role=str(values[16]) if values[16] is not None else None,
            escalation_triggered_at_utc=str(values[17]) if values[17] is not None else None,
        )


def _extract_selected_publication_ids(*, content_json: str) -> tuple[str, ...]:
    try:
        payload = json.loads(content_json)
    except (TypeError, ValueError):
        return ()

    if not isinstance(payload, dict):
        return ()

    raw_selected = payload.get("selected_publication_ids")
    if not isinstance(raw_selected, list):
        return ()

    return tuple(
        item.strip()
        for item in raw_selected
        if isinstance(item, str) and item.strip()
    )


def _decode_counts_json(raw: str) -> dict[str, int]:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}

    decoded: dict[str, int] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            decoded[key] = value
            continue
        if isinstance(value, float) and value.is_integer():
            decoded[key] = int(value)
    return decoded


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)