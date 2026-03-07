from __future__ import annotations

import json
import logging
import sqlite3
from hashlib import sha256
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isinf
from typing import Literal

from councilsense.app.parser_drift_policy import ParserDriftComparisonInput, evaluate_parser_drift
from councilsense.app.source_freshness_policy import (
    SourceFreshnessEvaluationInput,
    SourceFreshnessPolicyConfig,
    evaluate_source_freshness,
)


RunLifecycleStatus = Literal[
    "pending",
    "processed",
    "failed",
    "limited_confidence",
    "manual_review_needed",
]


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingRunRecord:
    id: str
    city_id: str
    cycle_id: str
    status: RunLifecycleStatus
    parser_version: str
    source_version: str
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True)
class StageOutcomeRecord:
    id: str
    run_id: str
    city_id: str
    meeting_id: str
    stage_name: str
    status: RunLifecycleStatus
    metadata_json: str | None
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True)
class ProcessingRunSourceRecord:
    id: str
    run_id: str
    city_id: str
    source_id: str
    source_type: str
    source_url: str
    parser_name: str
    parser_version: str
    recorded_at: str | None


@dataclass(frozen=True)
class ParserDriftEventRecord:
    id: str
    event_schema_version: str
    city_id: str
    source_id: str
    source_type: str
    source_url: str
    parser_name: str
    baseline_parser_name: str
    baseline_parser_version: str
    current_parser_name: str
    current_parser_version: str
    baseline_run_id: str
    run_id: str
    baseline_source_version: str
    current_source_version: str
    delta_context_json: str
    detected_at: str | None


@dataclass(frozen=True)
class SourceFreshnessBreachEventRecord:
    id: str
    event_schema_version: str
    city_id: str
    source_id: str
    source_type: str
    source_url: str
    run_id: str
    parser_drift_event_id: str | None
    severity: str
    threshold_age_hours: float
    last_success_age_hours: float
    last_success_at: str | None
    evaluated_at: str
    suppressed: bool
    suppression_reason: str | None
    maintenance_window_name: str | None
    maintenance_window_starts_at: str | None
    maintenance_window_ends_at: str | None
    triage_payload_json: str
    detected_at: str | None


class ProcessingRunRepository:
    _DRIFT_EVENT_SCHEMA_VERSION = "st016.parser_drift_event.v1"
    _FRESHNESS_EVENT_SCHEMA_VERSION = "st016.source_freshness_breach_event.v1"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_pending_run(
        self,
        *,
        run_id: str,
        city_id: str,
        cycle_id: str,
        freshness_policy_config: SourceFreshnessPolicyConfig | None = None,
        freshness_evaluated_at: str | None = None,
    ) -> ProcessingRunRecord:
        parser_version, source_version = self._derive_run_provenance(city_id=city_id)
        effective_freshness_policy = freshness_policy_config or SourceFreshnessPolicyConfig()
        evaluated_at = freshness_evaluated_at or datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO processing_runs (
                    id,
                    city_id,
                    cycle_id,
                    status,
                    parser_version,
                    source_version,
                    started_at
                )
                VALUES (?, ?, ?, 'pending', ?, ?, CURRENT_TIMESTAMP)
                """,
                (run_id, city_id, cycle_id, parser_version, source_version),
            )
            current_source_snapshots = self._snapshot_run_sources(run_id=run_id, city_id=city_id)
            self._emit_parser_drift_events(
                run_id=run_id,
                city_id=city_id,
                source_version=source_version,
                current_source_snapshots=current_source_snapshots,
            )
            self._emit_source_freshness_breach_events(
                run_id=run_id,
                city_id=city_id,
                current_source_snapshots=current_source_snapshots,
                evaluated_at=evaluated_at,
                policy_config=effective_freshness_policy,
            )

        return self.get_run(run_id=run_id)

    def mark_run_completed(self, *, run_id: str, status: RunLifecycleStatus) -> ProcessingRunRecord:
        if status == "pending":
            raise ValueError("Run final status must not be pending")

        with self._connection:
            self._connection.execute(
                """
                UPDATE processing_runs
                SET
                    status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, run_id),
            )

        return self.get_run(run_id=run_id)

    def get_run(self, *, run_id: str) -> ProcessingRunRecord:
        row = self._connection.execute(
            """
            SELECT id, city_id, cycle_id, status, parser_version, source_version, started_at, finished_at
            FROM processing_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Run not found: {run_id}")

        return ProcessingRunRecord(
            id=str(row[0]),
            city_id=str(row[1]),
            cycle_id=str(row[2]),
            status=str(row[3]),
            parser_version=str(row[4]),
            source_version=str(row[5]),
            started_at=str(row[6]) if row[6] is not None else None,
            finished_at=str(row[7]) if row[7] is not None else None,
        )

    def _derive_run_provenance(self, *, city_id: str) -> tuple[str, str]:
        rows = self._connection.execute(
            """
            SELECT id, source_type, source_url, parser_name, parser_version
            FROM city_sources
            WHERE city_id = ?
              AND enabled = 1
            ORDER BY source_type ASC, id ASC
            """,
            (city_id,),
        ).fetchall()

        if not rows:
            return ("unknown", "unknown")

        parser_version = "|".join(f"{str(row[3]).strip()}@{str(row[4]).strip()}" for row in rows)
        source_descriptor = [
            {
                "id": str(row[0]),
                "parser_name": str(row[3]),
                "parser_version": str(row[4]),
                "source_type": str(row[1]),
                "source_url": str(row[2]),
            }
            for row in rows
        ]
        source_fingerprint = sha256(
            json.dumps(source_descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12]
        return (parser_version, f"sources-sha256:{source_fingerprint}")

    def upsert_stage_outcome(
        self,
        *,
        outcome_id: str,
        run_id: str,
        city_id: str,
        meeting_id: str,
        stage_name: str,
        status: RunLifecycleStatus,
        metadata_json: str | None,
        started_at: str | None,
        finished_at: str | None,
    ) -> StageOutcomeRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO processing_stage_outcomes (
                    id,
                    run_id,
                    city_id,
                    meeting_id,
                    stage_name,
                    status,
                    metadata_json,
                    started_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, city_id, meeting_id, stage_name)
                DO UPDATE SET
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    outcome_id,
                    run_id,
                    city_id,
                    meeting_id,
                    stage_name,
                    status,
                    metadata_json,
                    started_at,
                    finished_at,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                run_id,
                city_id,
                meeting_id,
                stage_name,
                status,
                metadata_json,
                started_at,
                finished_at
            FROM processing_stage_outcomes
            WHERE run_id = ?
              AND city_id = ?
              AND meeting_id = ?
              AND stage_name = ?
            """,
            (run_id, city_id, meeting_id, stage_name),
        ).fetchone()
        assert row is not None

        return StageOutcomeRecord(
            id=str(row[0]),
            run_id=str(row[1]),
            city_id=str(row[2]),
            meeting_id=str(row[3]),
            stage_name=str(row[4]),
            status=str(row[5]),
            metadata_json=str(row[6]) if row[6] is not None else None,
            started_at=str(row[7]) if row[7] is not None else None,
            finished_at=str(row[8]) if row[8] is not None else None,
        )

    def list_stage_outcomes_for_run_city(self, *, run_id: str, city_id: str) -> tuple[StageOutcomeRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                run_id,
                city_id,
                meeting_id,
                stage_name,
                status,
                metadata_json,
                started_at,
                finished_at
            FROM processing_stage_outcomes
            WHERE run_id = ?
              AND city_id = ?
            ORDER BY meeting_id ASC, stage_name ASC
            """,
            (run_id, city_id),
        ).fetchall()
        return tuple(
            StageOutcomeRecord(
                id=str(row[0]),
                run_id=str(row[1]),
                city_id=str(row[2]),
                meeting_id=str(row[3]),
                stage_name=str(row[4]),
                status=str(row[5]),
                metadata_json=str(row[6]) if row[6] is not None else None,
                started_at=str(row[7]) if row[7] is not None else None,
                finished_at=str(row[8]) if row[8] is not None else None,
            )
            for row in rows
        )

    def get_stage_outcome(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting_id: str,
        stage_name: str,
    ) -> StageOutcomeRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                run_id,
                city_id,
                meeting_id,
                stage_name,
                status,
                metadata_json,
                started_at,
                finished_at
            FROM processing_stage_outcomes
            WHERE run_id = ?
              AND city_id = ?
              AND meeting_id = ?
              AND stage_name = ?
            """,
            (run_id, city_id, meeting_id, stage_name),
        ).fetchone()
        if row is None:
            return None

        return StageOutcomeRecord(
            id=str(row[0]),
            run_id=str(row[1]),
            city_id=str(row[2]),
            meeting_id=str(row[3]),
            stage_name=str(row[4]),
            status=str(row[5]),
            metadata_json=str(row[6]) if row[6] is not None else None,
            started_at=str(row[7]) if row[7] is not None else None,
            finished_at=str(row[8]) if row[8] is not None else None,
        )

    def list_parser_drift_events(
        self,
        *,
        city_id: str | None = None,
        source_id: str | None = None,
        parser_version: str | None = None,
        detected_from: str | None = None,
        detected_to: str | None = None,
        limit: int = 200,
    ) -> tuple[ParserDriftEventRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        clauses: list[str] = []
        params: list[object] = []

        if city_id is not None:
            clauses.append("city_id = ?")
            params.append(city_id)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if parser_version is not None:
            clauses.append("(baseline_parser_version = ? OR current_parser_version = ?)")
            params.extend((parser_version, parser_version))
        if detected_from is not None:
            clauses.append("detected_at >= ?")
            params.append(detected_from)
        if detected_to is not None:
            clauses.append("detected_at <= ?")
            params.append(detected_to)

        where_sql = ""
        if clauses:
            where_sql = f"WHERE {' AND '.join(clauses)}"

        params.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT
                id,
                event_schema_version,
                city_id,
                source_id,
                source_type,
                source_url,
                parser_name,
                baseline_parser_name,
                baseline_parser_version,
                current_parser_name,
                current_parser_version,
                baseline_run_id,
                run_id,
                baseline_source_version,
                current_source_version,
                delta_context_json,
                detected_at
            FROM parser_drift_events
            {where_sql}
            ORDER BY detected_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return tuple(
            ParserDriftEventRecord(
                id=str(row[0]),
                event_schema_version=str(row[1]),
                city_id=str(row[2]),
                source_id=str(row[3]),
                source_type=str(row[4]),
                source_url=str(row[5]),
                parser_name=str(row[6]),
                baseline_parser_name=str(row[7]),
                baseline_parser_version=str(row[8]),
                current_parser_name=str(row[9]),
                current_parser_version=str(row[10]),
                baseline_run_id=str(row[11]),
                run_id=str(row[12]),
                baseline_source_version=str(row[13]),
                current_source_version=str(row[14]),
                delta_context_json=str(row[15]),
                detected_at=str(row[16]) if row[16] is not None else None,
            )
            for row in rows
        )

    def list_source_freshness_breach_events(
        self,
        *,
        city_id: str | None = None,
        source_id: str | None = None,
        severity: str | None = None,
        suppressed: bool | None = None,
        detected_from: str | None = None,
        detected_to: str | None = None,
        limit: int = 200,
    ) -> tuple[SourceFreshnessBreachEventRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        clauses: list[str] = []
        params: list[object] = []

        if city_id is not None:
            clauses.append("city_id = ?")
            params.append(city_id)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if suppressed is not None:
            clauses.append("suppressed = ?")
            params.append(1 if suppressed else 0)
        if detected_from is not None:
            clauses.append("detected_at >= ?")
            params.append(detected_from)
        if detected_to is not None:
            clauses.append("detected_at <= ?")
            params.append(detected_to)

        where_sql = ""
        if clauses:
            where_sql = f"WHERE {' AND '.join(clauses)}"

        params.append(limit)
        rows = self._connection.execute(
            f"""
            SELECT
                id,
                event_schema_version,
                city_id,
                source_id,
                source_type,
                source_url,
                run_id,
                parser_drift_event_id,
                severity,
                threshold_age_hours,
                last_success_age_hours,
                last_success_at,
                evaluated_at,
                suppressed,
                suppression_reason,
                maintenance_window_name,
                maintenance_window_starts_at,
                maintenance_window_ends_at,
                triage_payload_json,
                detected_at
            FROM source_freshness_breach_events
            {where_sql}
            ORDER BY detected_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return tuple(
            SourceFreshnessBreachEventRecord(
                id=str(row[0]),
                event_schema_version=str(row[1]),
                city_id=str(row[2]),
                source_id=str(row[3]),
                source_type=str(row[4]),
                source_url=str(row[5]),
                run_id=str(row[6]),
                parser_drift_event_id=str(row[7]) if row[7] is not None else None,
                severity=str(row[8]),
                threshold_age_hours=float(row[9]),
                last_success_age_hours=float(row[10]),
                last_success_at=str(row[11]) if row[11] is not None else None,
                evaluated_at=str(row[12]),
                suppressed=bool(int(row[13])),
                suppression_reason=str(row[14]) if row[14] is not None else None,
                maintenance_window_name=str(row[15]) if row[15] is not None else None,
                maintenance_window_starts_at=str(row[16]) if row[16] is not None else None,
                maintenance_window_ends_at=str(row[17]) if row[17] is not None else None,
                triage_payload_json=str(row[18]),
                detected_at=str(row[19]) if row[19] is not None else None,
            )
            for row in rows
        )

    def get_latest_run_confidence_score(self, *, run_id: str) -> float | None:
        rows = self._connection.execute(
            """
            SELECT metadata_json
            FROM processing_stage_outcomes
            WHERE run_id = ?
              AND metadata_json IS NOT NULL
            ORDER BY
                CASE stage_name
                    WHEN 'publish' THEN 0
                    WHEN 'summarize' THEN 1
                    ELSE 2
                END ASC,
                COALESCE(finished_at, started_at, created_at) DESC,
                id DESC
            """,
            (run_id,),
        ).fetchall()

        for row in rows:
            metadata_json = row[0]
            if metadata_json is None:
                continue
            try:
                metadata = json.loads(str(metadata_json))
            except json.JSONDecodeError:
                continue
            if not isinstance(metadata, dict):
                continue

            score = metadata.get("confidence_score")
            if score is None:
                score = metadata.get("confidence")
            if score is None:
                score = metadata.get("score")

            if isinstance(score, bool):
                continue
            if isinstance(score, (int, float)):
                numeric_score = float(score)
                if 0.0 <= numeric_score <= 1.0:
                    return numeric_score

        return None

    def _snapshot_run_sources(self, *, run_id: str, city_id: str) -> tuple[ProcessingRunSourceRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT id, source_type, source_url, parser_name, parser_version
            FROM city_sources
            WHERE city_id = ?
              AND enabled = 1
            ORDER BY source_type ASC, id ASC
            """,
            (city_id,),
        ).fetchall()

        snapshots: list[ProcessingRunSourceRecord] = []
        for row in rows:
            source_id = str(row[0])
            source_type = str(row[1])
            source_url = str(row[2])
            parser_name = str(row[3])
            parser_version = str(row[4])
            snapshot_id = f"prs-{sha256(f'{run_id}:{source_id}'.encode('utf-8')).hexdigest()[:16]}"

            self._connection.execute(
                """
                INSERT INTO processing_run_sources (
                    id,
                    run_id,
                    city_id,
                    source_id,
                    source_type,
                    source_url,
                    parser_name,
                    parser_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, source_id)
                DO UPDATE SET
                    source_type = excluded.source_type,
                    source_url = excluded.source_url,
                    parser_name = excluded.parser_name,
                    parser_version = excluded.parser_version,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    snapshot_id,
                    run_id,
                    city_id,
                    source_id,
                    source_type,
                    source_url,
                    parser_name,
                    parser_version,
                ),
            )

            snapshot_row = self._connection.execute(
                """
                SELECT id, run_id, city_id, source_id, source_type, source_url, parser_name, parser_version, recorded_at
                FROM processing_run_sources
                WHERE run_id = ?
                  AND source_id = ?
                """,
                (run_id, source_id),
            ).fetchone()
            assert snapshot_row is not None
            snapshots.append(
                ProcessingRunSourceRecord(
                    id=str(snapshot_row[0]),
                    run_id=str(snapshot_row[1]),
                    city_id=str(snapshot_row[2]),
                    source_id=str(snapshot_row[3]),
                    source_type=str(snapshot_row[4]),
                    source_url=str(snapshot_row[5]),
                    parser_name=str(snapshot_row[6]),
                    parser_version=str(snapshot_row[7]),
                    recorded_at=str(snapshot_row[8]) if snapshot_row[8] is not None else None,
                )
            )

        return tuple(snapshots)

    def _emit_parser_drift_events(
        self,
        *,
        run_id: str,
        city_id: str,
        source_version: str,
        current_source_snapshots: tuple[ProcessingRunSourceRecord, ...],
    ) -> None:
        for current in current_source_snapshots:
            baseline_row = self._connection.execute(
                """
                SELECT
                    prs.run_id,
                    prs.source_type,
                    prs.source_url,
                    prs.parser_name,
                    prs.parser_version,
                    pr.source_version
                FROM processing_run_sources prs
                JOIN processing_runs pr ON pr.id = prs.run_id
                WHERE prs.city_id = ?
                  AND prs.source_id = ?
                  AND prs.run_id <> ?
                                ORDER BY pr.cycle_id DESC, COALESCE(pr.started_at, pr.created_at) DESC, prs.recorded_at DESC, prs.id DESC
                LIMIT 1
                """,
                (city_id, current.source_id, run_id),
            ).fetchone()
            if baseline_row is None:
                continue

            baseline_run_id = str(baseline_row[0])
            baseline_source_type = str(baseline_row[1])
            baseline_source_url = str(baseline_row[2])
            baseline_parser_name = str(baseline_row[3])
            baseline_parser_version = str(baseline_row[4])
            baseline_source_version = str(baseline_row[5])

            if (
                baseline_parser_name == current.parser_name
                and baseline_parser_version == current.parser_version
            ):
                continue

            changed_fields = evaluate_parser_drift(
                ParserDriftComparisonInput(
                    baseline_parser_name=baseline_parser_name,
                    baseline_parser_version=baseline_parser_version,
                    current_parser_name=current.parser_name,
                    current_parser_version=current.parser_version,
                )
            )
            if changed_fields is None:
                continue

            delta_context = {
                "changed_fields": list(changed_fields),
                "baseline": {
                    "run_id": baseline_run_id,
                    "source_type": baseline_source_type,
                    "source_url": baseline_source_url,
                    "parser_name": baseline_parser_name,
                    "parser_version": baseline_parser_version,
                    "source_version": baseline_source_version,
                },
                "current": {
                    "run_id": run_id,
                    "source_type": current.source_type,
                    "source_url": current.source_url,
                    "parser_name": current.parser_name,
                    "parser_version": current.parser_version,
                    "source_version": source_version,
                },
            }
            drift_event_id = f"pde-{sha256(f'{run_id}:{current.source_id}'.encode('utf-8')).hexdigest()[:16]}"

            self._connection.execute(
                """
                INSERT INTO parser_drift_events (
                    id,
                    event_schema_version,
                    city_id,
                    source_id,
                    source_type,
                    source_url,
                    parser_name,
                    baseline_parser_name,
                    baseline_parser_version,
                    current_parser_name,
                    current_parser_version,
                    baseline_run_id,
                    run_id,
                    baseline_source_version,
                    current_source_version,
                    delta_context_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, source_id)
                DO UPDATE SET
                    source_type = excluded.source_type,
                    source_url = excluded.source_url,
                    parser_name = excluded.parser_name,
                    baseline_parser_name = excluded.baseline_parser_name,
                    baseline_parser_version = excluded.baseline_parser_version,
                    current_parser_name = excluded.current_parser_name,
                    current_parser_version = excluded.current_parser_version,
                    baseline_run_id = excluded.baseline_run_id,
                    baseline_source_version = excluded.baseline_source_version,
                    current_source_version = excluded.current_source_version,
                    delta_context_json = excluded.delta_context_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    drift_event_id,
                    self._DRIFT_EVENT_SCHEMA_VERSION,
                    city_id,
                    current.source_id,
                    current.source_type,
                    current.source_url,
                    current.parser_name,
                    baseline_parser_name,
                    baseline_parser_version,
                    current.parser_name,
                    current.parser_version,
                    baseline_run_id,
                    run_id,
                    baseline_source_version,
                    source_version,
                    json.dumps(delta_context, sort_keys=True, separators=(",", ":")),
                ),
            )

    def _emit_source_freshness_breach_events(
        self,
        *,
        run_id: str,
        city_id: str,
        current_source_snapshots: tuple[ProcessingRunSourceRecord, ...],
        evaluated_at: str,
        policy_config: SourceFreshnessPolicyConfig,
    ) -> None:
        for source_snapshot in current_source_snapshots:
            source_row = self._connection.execute(
                """
                SELECT last_success_at
                FROM city_sources
                WHERE id = ?
                """,
                (source_snapshot.source_id,),
            ).fetchone()
            if source_row is None:
                continue

            last_success_at = str(source_row[0]) if source_row[0] is not None else None
            decision = evaluate_source_freshness(
                policy_input=SourceFreshnessEvaluationInput(
                    city_id=city_id,
                    source_id=source_snapshot.source_id,
                    source_type=source_snapshot.source_type,
                    evaluated_at=evaluated_at,
                    last_success_at=last_success_at,
                ),
                config=policy_config,
            )
            if decision is None:
                continue

            parser_drift_row = self._connection.execute(
                """
                SELECT id
                FROM parser_drift_events
                WHERE run_id = ?
                  AND source_id = ?
                ORDER BY detected_at DESC, id DESC
                LIMIT 1
                """,
                (run_id, source_snapshot.source_id),
            ).fetchone()

            parser_drift_event_id = str(parser_drift_row[0]) if parser_drift_row is not None else None
            source_key = f"{city_id}:{source_snapshot.source_id}"
            event_id = f"sfe-{sha256(f'{run_id}:{source_key}'.encode('utf-8')).hexdigest()[:16]}"

            normalized_age = decision.last_success_age_hours
            if isinf(normalized_age):
                normalized_age = 999999.0

            triage_payload = {
                "alert_class": "source_freshness",
                "alert_id": f"source-freshness-regression-{decision.severity}",
                "city_id": city_id,
                "source_id": source_snapshot.source_id,
                "run_id": run_id,
                "meeting_id": "run-scope",
                "stage": "ingest",
                "outcome": "freshness_regression",
                "environment": "local",
                "observed_value": normalized_age,
                "threshold_value": decision.threshold_age_hours,
                "evaluation_window": policy_config.evaluation_window,
                "triggered_at_utc": evaluated_at,
                "source_type": source_snapshot.source_type,
                "source_url": source_snapshot.source_url,
                "last_success_at": last_success_at,
                "last_success_age_hours": normalized_age,
                "suppressed": decision.suppressed,
                "suppression_reason": decision.suppression_reason,
                "maintenance_window_name": decision.suppression_window_name,
                "maintenance_window_starts_at": decision.suppression_window_starts_at,
                "maintenance_window_ends_at": decision.suppression_window_ends_at,
                "parser_drift_event_id": parser_drift_event_id,
            }

            self._connection.execute(
                """
                INSERT INTO source_freshness_breach_events (
                    id,
                    event_schema_version,
                    city_id,
                    source_id,
                    source_type,
                    source_url,
                    run_id,
                    parser_drift_event_id,
                    severity,
                    threshold_age_hours,
                    last_success_age_hours,
                    last_success_at,
                    evaluated_at,
                    suppressed,
                    suppression_reason,
                    maintenance_window_name,
                    maintenance_window_starts_at,
                    maintenance_window_ends_at,
                    triage_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id, source_id)
                DO UPDATE SET
                    parser_drift_event_id = excluded.parser_drift_event_id,
                    severity = excluded.severity,
                    threshold_age_hours = excluded.threshold_age_hours,
                    last_success_age_hours = excluded.last_success_age_hours,
                    last_success_at = excluded.last_success_at,
                    evaluated_at = excluded.evaluated_at,
                    suppressed = excluded.suppressed,
                    suppression_reason = excluded.suppression_reason,
                    maintenance_window_name = excluded.maintenance_window_name,
                    maintenance_window_starts_at = excluded.maintenance_window_starts_at,
                    maintenance_window_ends_at = excluded.maintenance_window_ends_at,
                    triage_payload_json = excluded.triage_payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    event_id,
                    self._FRESHNESS_EVENT_SCHEMA_VERSION,
                    city_id,
                    source_snapshot.source_id,
                    source_snapshot.source_type,
                    source_snapshot.source_url,
                    run_id,
                    parser_drift_event_id,
                    decision.severity,
                    decision.threshold_age_hours,
                    normalized_age,
                    last_success_at,
                    evaluated_at,
                    1 if decision.suppressed else 0,
                    decision.suppression_reason,
                    decision.suppression_window_name,
                    decision.suppression_window_starts_at,
                    decision.suppression_window_ends_at,
                    json.dumps(triage_payload, sort_keys=True, separators=(",", ":")),
                ),
            )


class ProcessingLifecycleService:
    def __init__(self, repository: ProcessingRunRepository) -> None:
        self._repository = repository

    def mark_processed(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="processed")

    def mark_failed(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="failed")

    def mark_limited_confidence(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="limited_confidence")

    def mark_manual_review_needed(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="manual_review_needed")

    def mark_completed_from_confidence_policy(
        self,
        *,
        run_id: str,
        manual_review_threshold: float = 0.6,
        warn_threshold: float = 0.8,
    ) -> ProcessingRunRecord:
        from councilsense.app.source_health_policy import ConfidencePolicyConfig, evaluate_confidence_policy

        decision = evaluate_confidence_policy(
            confidence_score=self._repository.get_latest_run_confidence_score(run_id=run_id),
            config=ConfidencePolicyConfig(
                manual_review_threshold=manual_review_threshold,
                warn_threshold=warn_threshold,
            ),
        )

        if decision.manual_review_needed:
            run = self._repository.get_run(run_id=run_id)
            logger.info(
                "pipeline_manual_review_needed",
                extra={
                    "event": {
                        "event_name": "pipeline_manual_review_needed",
                        "city_id": run.city_id,
                        "meeting_id": "run-scope",
                        "run_id": run.id,
                        "dedupe_key": f"pipeline-run:{run.id}:manual-review-needed",
                        "stage": "publish",
                        "outcome": "failure",
                        "run_status": "manual_review_needed",
                        "reason_code": decision.reason_code,
                        "confidence_score": decision.confidence_score,
                    }
                },
            )
            return self.mark_manual_review_needed(run_id=run_id)

        return self.mark_processed(run_id=run_id)
