from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
import json
import sqlite3
from typing import Any, Callable
from uuid import uuid4

from councilsense.app.ecr_audit_sampling import (
    AuditSampleCandidate,
    WeeklyAuditSampleResult,
    select_weekly_audit_sample,
)

REPORT_VERSION = "st-015-weekly-audit-report-v1"
FORMULA_VERSION = "st-015-ecr-formula-v1"
DEFAULT_OWNER_ROLE = "ops-quality-oncall"
DEFAULT_SAMPLE_SIZE = 60
DEFAULT_SEED_SALT = "v1"
DEFAULT_MIN_CITY_SLOTS = 3
DEFAULT_MIN_SOURCE_SLOTS = 2


@dataclass(frozen=True)
class EcrAuditRunResult:
    run_id: str
    status: str
    audit_week_start_utc: datetime
    audit_week_end_utc: datetime
    report_artifact_uri: str | None


@dataclass(frozen=True)
class WeeklyEcrTrendPoint:
    audit_week_start_utc: str
    ecr: float
    claim_count: int
    claims_with_evidence_count: int
    artifact_uri: str


class WeeklyEcrAuditJob:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def run_scheduled_weekly_audit(
        self,
        *,
        scheduler_triggered_at_utc: datetime | None = None,
        owner_role: str = DEFAULT_OWNER_ROLE,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
        seed_salt: str = DEFAULT_SEED_SALT,
        min_city_slots: int = DEFAULT_MIN_CITY_SLOTS,
        min_source_slots: int = DEFAULT_MIN_SOURCE_SLOTS,
    ) -> EcrAuditRunResult:
        triggered_at = scheduler_triggered_at_utc or self._now_provider()
        triggered_at_utc = _normalize_utc_datetime(triggered_at)
        current_week_start = _monday_start_utc(triggered_at_utc)
        audit_week_start = current_week_start - timedelta(days=7)
        return self.run_for_week(
            audit_week_start_utc=audit_week_start,
            scheduler_triggered_at_utc=triggered_at_utc,
            owner_role=owner_role,
            sample_size=sample_size,
            seed_salt=seed_salt,
            min_city_slots=min_city_slots,
            min_source_slots=min_source_slots,
        )

    def run_for_week(
        self,
        *,
        audit_week_start_utc: datetime,
        scheduler_triggered_at_utc: datetime | None = None,
        owner_role: str = DEFAULT_OWNER_ROLE,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
        seed_salt: str = DEFAULT_SEED_SALT,
        min_city_slots: int = DEFAULT_MIN_CITY_SLOTS,
        min_source_slots: int = DEFAULT_MIN_SOURCE_SLOTS,
    ) -> EcrAuditRunResult:
        window_start = _normalize_window_start_utc(audit_week_start_utc)
        window_end = window_start + timedelta(days=7)
        triggered_at_utc = _normalize_utc_datetime(scheduler_triggered_at_utc or self._now_provider())
        started_at_utc = _normalize_utc_datetime(self._now_provider())

        run_id = f"ecrrun-{uuid4().hex}"
        runtime_metadata = {
            "started_at_utc": started_at_utc.isoformat(),
            "sample_size_requested": sample_size,
            "failure_count": 0,
        }

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ecr_audit_runs (
                    id,
                    audit_week_start_utc,
                    audit_week_end_utc,
                    status,
                    owner_role,
                    scheduler_triggered_at_utc,
                    started_at_utc,
                    formula_version,
                    report_version,
                    runtime_metadata_json
                )
                VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    window_start.isoformat(),
                    window_end.isoformat(),
                    owner_role,
                    triggered_at_utc.isoformat(),
                    started_at_utc.isoformat(),
                    FORMULA_VERSION,
                    REPORT_VERSION,
                    json.dumps(runtime_metadata, separators=(",", ":"), sort_keys=True),
                ),
            )

        try:
            sample_result = self._select_sample(
                window_start_utc=window_start,
                sample_size=sample_size,
                seed_salt=seed_salt,
                min_city_slots=min_city_slots,
                min_source_slots=min_source_slots,
            )
            selected_publication_ids = tuple(item.publication_id for item in sample_result.selected)
            claims_with_evidence_count, claim_count = self._compute_claim_metrics(selected_publication_ids)
            ecr = round((claims_with_evidence_count / claim_count), 4) if claim_count > 0 else 0.0
            confidence_buckets = self._compute_confidence_bucket_breakdown(selected_publication_ids)

            finished_at_utc = _normalize_utc_datetime(self._now_provider())
            duration_ms = max(
                0,
                int((finished_at_utc - started_at_utc).total_seconds() * 1000),
            )
            runtime_metadata.update(
                {
                    "finished_at_utc": finished_at_utc.isoformat(),
                    "duration_ms": duration_ms,
                    "sample_size_actual": sample_result.sample_size_actual,
                    "eligible_frame_count": sample_result.eligible_frame_count,
                    "malformed_exclusion_count": len(sample_result.malformed_exclusions),
                }
            )

            artifact_uri = f"quality/ecr-audits/{window_start.date().isoformat()}/weekly-ecr-report.json"
            report_payload = self._build_report_payload(
                sample_result=sample_result,
                scheduler_triggered_at_utc=triggered_at_utc,
                generated_at_utc=finished_at_utc,
                owner_role=owner_role,
                claim_count=claim_count,
                claims_with_evidence_count=claims_with_evidence_count,
                ecr=ecr,
                confidence_buckets=confidence_buckets,
                selected_publication_ids=selected_publication_ids,
            )

            with self._connection:
                artifact_id = f"ecrartifact-{uuid4().hex}"
                self._connection.execute(
                    """
                    INSERT INTO ecr_audit_report_artifacts (
                        id,
                        run_id,
                        audit_week_start_utc,
                        audit_week_end_utc,
                        artifact_uri,
                        report_version,
                        formula_version,
                        generated_at_utc,
                        ecr,
                        claim_count,
                        claims_with_evidence_count,
                        content_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(audit_week_start_utc) DO UPDATE SET
                        run_id = excluded.run_id,
                        audit_week_end_utc = excluded.audit_week_end_utc,
                        artifact_uri = excluded.artifact_uri,
                        report_version = excluded.report_version,
                        formula_version = excluded.formula_version,
                        generated_at_utc = excluded.generated_at_utc,
                        ecr = excluded.ecr,
                        claim_count = excluded.claim_count,
                        claims_with_evidence_count = excluded.claims_with_evidence_count,
                        content_json = excluded.content_json
                    """,
                    (
                        artifact_id,
                        run_id,
                        window_start.isoformat(),
                        window_end.isoformat(),
                        artifact_uri,
                        REPORT_VERSION,
                        FORMULA_VERSION,
                        finished_at_utc.isoformat(),
                        ecr,
                        claim_count,
                        claims_with_evidence_count,
                        json.dumps(report_payload, separators=(",", ":"), sort_keys=True),
                    ),
                )
                self._connection.execute(
                    """
                    UPDATE ecr_audit_runs
                    SET
                        status = 'completed',
                        finished_at_utc = ?,
                        seed = ?,
                        sample_size_requested = ?,
                        sample_size_actual = ?,
                        eligible_frame_count = ?,
                        malformed_exclusion_count = ?,
                        report_artifact_uri = ?,
                        runtime_metadata_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        finished_at_utc.isoformat(),
                        sample_result.seed,
                        sample_result.sample_size_requested,
                        sample_result.sample_size_actual,
                        sample_result.eligible_frame_count,
                        len(sample_result.malformed_exclusions),
                        artifact_uri,
                        json.dumps(runtime_metadata, separators=(",", ":"), sort_keys=True),
                        run_id,
                    ),
                )

            return EcrAuditRunResult(
                run_id=run_id,
                status="completed",
                audit_week_start_utc=window_start,
                audit_week_end_utc=window_end,
                report_artifact_uri=artifact_uri,
            )
        except Exception as exc:
            finished_at_utc = _normalize_utc_datetime(self._now_provider())
            runtime_metadata.update(
                {
                    "finished_at_utc": finished_at_utc.isoformat(),
                    "failure_count": 1,
                }
            )
            with self._connection:
                self._connection.execute(
                    """
                    UPDATE ecr_audit_runs
                    SET
                        status = 'failed_retryable',
                        finished_at_utc = ?,
                        error_code = 'ecr_audit_generation_failed_retryable',
                        error_message = ?,
                        runtime_metadata_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        finished_at_utc.isoformat(),
                        str(exc),
                        json.dumps(runtime_metadata, separators=(",", ":"), sort_keys=True),
                        run_id,
                    ),
                )
            return EcrAuditRunResult(
                run_id=run_id,
                status="failed_retryable",
                audit_week_start_utc=window_start,
                audit_week_end_utc=window_end,
                report_artifact_uri=None,
            )

    def backfill_weeks(
        self,
        *,
        audit_week_starts_utc: tuple[datetime, ...],
        scheduler_triggered_at_utc: datetime | None = None,
        owner_role: str = DEFAULT_OWNER_ROLE,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
        seed_salt: str = DEFAULT_SEED_SALT,
        min_city_slots: int = DEFAULT_MIN_CITY_SLOTS,
        min_source_slots: int = DEFAULT_MIN_SOURCE_SLOTS,
    ) -> tuple[EcrAuditRunResult, ...]:
        ordered_week_starts = tuple(sorted(audit_week_starts_utc))
        results: list[EcrAuditRunResult] = []
        for week_start in ordered_week_starts:
            result = self.run_for_week(
                audit_week_start_utc=week_start,
                scheduler_triggered_at_utc=scheduler_triggered_at_utc,
                owner_role=owner_role,
                sample_size=sample_size,
                seed_salt=seed_salt,
                min_city_slots=min_city_slots,
                min_source_slots=min_source_slots,
            )
            results.append(result)
        return tuple(results)

    def list_weekly_ecr_trend(self, *, limit: int = 26) -> tuple[WeeklyEcrTrendPoint, ...]:
        rows = self._connection.execute(
            """
            SELECT
                audit_week_start_utc,
                ecr,
                claim_count,
                claims_with_evidence_count,
                artifact_uri
            FROM ecr_audit_report_artifacts
            ORDER BY audit_week_start_utc DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            WeeklyEcrTrendPoint(
                audit_week_start_utc=str(row[0]),
                ecr=float(row[1]),
                claim_count=int(row[2]),
                claims_with_evidence_count=int(row[3]),
                artifact_uri=str(row[4]),
            )
            for row in rows
        )

    def _select_sample(
        self,
        *,
        window_start_utc: datetime,
        sample_size: int,
        seed_salt: str,
        min_city_slots: int,
        min_source_slots: int,
    ) -> WeeklyAuditSampleResult:
        candidates = self._load_candidates(window_start_utc=window_start_utc)
        return select_weekly_audit_sample(
            candidates,
            window_start_utc=window_start_utc,
            sample_size=sample_size,
            seed_salt=seed_salt,
            min_city_slots=min_city_slots,
            min_source_slots=min_source_slots,
        )

    def _load_candidates(self, *, window_start_utc: datetime) -> tuple[AuditSampleCandidate, ...]:
        window_end_utc = window_start_utc + timedelta(days=7)
        rows = self._connection.execute(
            """
            SELECT
                sp.id,
                sp.meeting_id,
                m.city_id,
                sp.publication_status,
                sp.published_at,
                pso.metadata_json
            FROM summary_publications sp
            JOIN meetings m ON m.id = sp.meeting_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = sp.publish_stage_outcome_id
            WHERE sp.published_at >= ? AND sp.published_at < ?
            ORDER BY sp.published_at ASC, sp.id ASC
            """,
            (window_start_utc.isoformat(), window_end_utc.isoformat()),
        ).fetchall()

        fallback_source_ids = self._load_fallback_source_ids_by_city()

        candidates: list[AuditSampleCandidate] = []
        for row in rows:
            publication_id = str(row[0])
            meeting_id = str(row[1])
            city_id = str(row[2])
            publication_status = str(row[3])
            published_at = _parse_db_timestamp(str(row[4]) if row[4] is not None else None)
            metadata_json = str(row[5]) if row[5] is not None else None

            source_id = _extract_source_id_from_metadata(metadata_json)
            if source_id is None:
                source_id = fallback_source_ids.get(city_id, "")

            candidates.append(
                AuditSampleCandidate(
                    publication_id=publication_id,
                    meeting_id=meeting_id,
                    city_id=city_id,
                    source_id=source_id,
                    publication_status=publication_status,
                    published_at=published_at,
                )
            )

        return tuple(candidates)

    def _load_fallback_source_ids_by_city(self) -> dict[str, str]:
        rows = self._connection.execute(
            """
            SELECT city_id, id
            FROM city_sources
            WHERE enabled = 1
            ORDER BY city_id ASC, id ASC
            """
        ).fetchall()

        grouped: dict[str, list[str]] = {}
        for row in rows:
            city_id = str(row[0])
            source_id = str(row[1])
            grouped.setdefault(city_id, []).append(source_id)

        return {
            city_id: source_ids[0]
            for city_id, source_ids in grouped.items()
            if len(source_ids) == 1
        }

    def _compute_claim_metrics(self, selected_publication_ids: tuple[str, ...]) -> tuple[int, int]:
        if not selected_publication_ids:
            return (0, 0)

        placeholders = ",".join("?" for _ in selected_publication_ids)
        claim_count_row = self._connection.execute(
            f"""
            SELECT COUNT(*)
            FROM publication_claims
            WHERE publication_id IN ({placeholders})
            """,
            selected_publication_ids,
        ).fetchone()
        claims_with_evidence_row = self._connection.execute(
            f"""
            SELECT COUNT(DISTINCT pc.id)
            FROM publication_claims pc
            JOIN claim_evidence_pointers cep ON cep.claim_id = pc.id
            WHERE pc.publication_id IN ({placeholders})
            """,
            selected_publication_ids,
        ).fetchone()

        claim_count = int(claim_count_row[0]) if claim_count_row is not None else 0
        claims_with_evidence_count = int(claims_with_evidence_row[0]) if claims_with_evidence_row is not None else 0
        return (claims_with_evidence_count, claim_count)

    def _compute_confidence_bucket_breakdown(self, selected_publication_ids: tuple[str, ...]) -> dict[str, dict[str, float | int]]:
        if not selected_publication_ids:
            return {}

        placeholders = ",".join("?" for _ in selected_publication_ids)
        rows = self._connection.execute(
            f"""
            SELECT
                sp.confidence_label,
                COUNT(DISTINCT sp.id) AS publication_count,
                COUNT(pc.id) AS claim_count,
                COUNT(DISTINCT CASE WHEN cep.id IS NOT NULL THEN pc.id END) AS claims_with_evidence_count
            FROM summary_publications sp
            LEFT JOIN publication_claims pc ON pc.publication_id = sp.id
            LEFT JOIN claim_evidence_pointers cep ON cep.claim_id = pc.id
            WHERE sp.id IN ({placeholders})
            GROUP BY sp.confidence_label
            ORDER BY sp.confidence_label ASC
            """,
            selected_publication_ids,
        ).fetchall()

        buckets: dict[str, dict[str, float | int]] = {}
        for row in rows:
            confidence_label = str(row[0])
            publication_count = int(row[1])
            claim_count = int(row[2])
            claims_with_evidence_count = int(row[3])
            bucket_ecr = round((claims_with_evidence_count / claim_count), 4) if claim_count > 0 else 0.0
            buckets[confidence_label] = {
                "publication_count": publication_count,
                "claim_count": claim_count,
                "claims_with_evidence_count": claims_with_evidence_count,
                "ecr": bucket_ecr,
            }
        return buckets

    def _build_report_payload(
        self,
        *,
        sample_result: WeeklyAuditSampleResult,
        scheduler_triggered_at_utc: datetime,
        generated_at_utc: datetime,
        owner_role: str,
        claim_count: int,
        claims_with_evidence_count: int,
        ecr: float,
        confidence_buckets: dict[str, dict[str, float | int]],
        selected_publication_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "report_version": REPORT_VERSION,
            "formula_version": FORMULA_VERSION,
            "audit_week_start_utc": sample_result.window_start_utc.isoformat(),
            "audit_week_end_utc": sample_result.window_end_utc.isoformat(),
            "generated_at_utc": generated_at_utc.isoformat(),
            "scheduler_triggered_at_utc": scheduler_triggered_at_utc.isoformat(),
            "owner_role": owner_role,
            "seed": sample_result.seed,
            "sample_size_requested": sample_result.sample_size_requested,
            "sample_size_actual": sample_result.sample_size_actual,
            "eligible_frame_count": sample_result.eligible_frame_count,
            "malformed_exclusion_count": len(sample_result.malformed_exclusions),
            "malformed_exclusions": [
                {
                    "publication_id": item.publication_id,
                    "reason_code": item.reason_code,
                }
                for item in sample_result.malformed_exclusions
            ],
            "representativeness": {
                "target_city_slots": sample_result.representativeness.target_city_slots,
                "target_source_slots": sample_result.representativeness.target_source_slots,
                "achieved_city_slots": sample_result.representativeness.achieved_city_slots,
                "achieved_source_slots": sample_result.representativeness.achieved_source_slots,
                "degraded": sample_result.representativeness.is_degraded,
            },
            "ecr": ecr,
            "claim_count": claim_count,
            "claims_with_evidence_count": claims_with_evidence_count,
            "selected_publication_ids": list(selected_publication_ids),
            "confidence_buckets": confidence_buckets,
        }


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


def _normalize_window_start_utc(window_start_utc: datetime) -> datetime:
    normalized = _normalize_utc_datetime(window_start_utc)
    if normalized.hour != 0 or normalized.minute != 0 or normalized.second != 0 or normalized.microsecond != 0:
        raise ValueError("audit_week_start_utc must be at 00:00:00 UTC")
    if normalized.weekday() != 0:
        raise ValueError("audit_week_start_utc must be a Monday")
    return normalized


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _monday_start_utc(value: datetime) -> datetime:
    normalized = _normalize_utc_datetime(value)
    return datetime(
        year=normalized.year,
        month=normalized.month,
        day=normalized.day,
        tzinfo=timezone.utc,
    ) - timedelta(days=normalized.weekday())


def _parse_db_timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1)

    normalized = value.strip()
    if not normalized:
        return datetime(1970, 1, 1)

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime(1970, 1, 1)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
