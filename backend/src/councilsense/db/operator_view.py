from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorSourceRecord:
    source_id: str
    city_id: str
    city_slug: str
    source_type: str
    source_url: str
    health_status: str
    failure_streak: int
    parser_name: str
    parser_version: str
    last_attempt_at: str | None
    last_success_at: str | None
    last_failure_at: str | None
    last_failure_reason: str | None


@dataclass(frozen=True)
class OperatorManualReviewRunRecord:
    run_id: str
    city_id: str
    city_slug: str
    cycle_id: str
    status: str
    parser_version: str
    source_version: str
    started_at: str | None
    finished_at: str | None
    confidence_score: float | None


class OperatorViewRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_stale_sources(self, *, stale_before: str) -> tuple[OperatorSourceRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                cs.id,
                cs.city_id,
                c.slug,
                cs.source_type,
                cs.source_url,
                cs.health_status,
                cs.failure_streak,
                cs.parser_name,
                cs.parser_version,
                cs.last_attempt_at,
                cs.last_success_at,
                cs.last_failure_at,
                cs.last_failure_reason
            FROM city_sources cs
            JOIN cities c ON c.id = cs.city_id
            WHERE c.enabled = 1
              AND cs.enabled = 1
              AND (
                cs.last_success_at IS NULL
                OR cs.last_success_at < ?
              )
            ORDER BY c.priority_tier ASC, c.id ASC, cs.source_type ASC, cs.id ASC
            """,
            (stale_before,),
        ).fetchall()
        return tuple(self._to_source_record(row) for row in rows)

    def list_failing_sources(self) -> tuple[OperatorSourceRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                cs.id,
                cs.city_id,
                c.slug,
                cs.source_type,
                cs.source_url,
                cs.health_status,
                cs.failure_streak,
                cs.parser_name,
                cs.parser_version,
                cs.last_attempt_at,
                cs.last_success_at,
                cs.last_failure_at,
                cs.last_failure_reason
            FROM city_sources cs
            JOIN cities c ON c.id = cs.city_id
            WHERE c.enabled = 1
              AND cs.enabled = 1
              AND cs.health_status = 'failing'
            ORDER BY c.priority_tier ASC, c.id ASC, cs.source_type ASC, cs.id ASC
            """
        ).fetchall()
        return tuple(self._to_source_record(row) for row in rows)

    def list_manual_review_needed_runs(self, *, limit: int = 100) -> tuple[OperatorManualReviewRunRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                pr.id,
                pr.city_id,
                c.slug,
                pr.cycle_id,
                pr.status,
                pr.parser_version,
                pr.source_version,
                pr.started_at,
                pr.finished_at,
                (
                    SELECT pso.metadata_json
                    FROM processing_stage_outcomes pso
                    WHERE pso.run_id = pr.id
                      AND pso.metadata_json IS NOT NULL
                    ORDER BY
                        CASE pso.stage_name
                            WHEN 'publish' THEN 0
                            WHEN 'summarize' THEN 1
                            ELSE 2
                        END ASC,
                        COALESCE(pso.finished_at, pso.started_at, pso.created_at) DESC,
                        pso.id DESC
                    LIMIT 1
                ) AS latest_metadata_json
            FROM processing_runs pr
            JOIN cities c ON c.id = pr.city_id
            WHERE c.enabled = 1
              AND pr.status = 'manual_review_needed'
            ORDER BY COALESCE(pr.finished_at, pr.started_at, pr.created_at) DESC, pr.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(self._to_manual_review_record(row) for row in rows)

    @staticmethod
    def _to_source_record(row: sqlite3.Row | tuple[object, ...]) -> OperatorSourceRecord:
        return OperatorSourceRecord(
            source_id=str(row[0]),
            city_id=str(row[1]),
            city_slug=str(row[2]),
            source_type=str(row[3]),
            source_url=str(row[4]),
            health_status=str(row[5]),
            failure_streak=int(row[6]),
            parser_name=str(row[7]),
            parser_version=str(row[8]),
            last_attempt_at=str(row[9]) if row[9] is not None else None,
            last_success_at=str(row[10]) if row[10] is not None else None,
            last_failure_at=str(row[11]) if row[11] is not None else None,
            last_failure_reason=str(row[12]) if row[12] is not None else None,
        )

    @staticmethod
    def _to_manual_review_record(
        row: sqlite3.Row | tuple[object, ...],
    ) -> OperatorManualReviewRunRecord:
        metadata_json = str(row[9]) if row[9] is not None else None
        confidence_score = OperatorViewRepository._extract_confidence_score(metadata_json)
        return OperatorManualReviewRunRecord(
            run_id=str(row[0]),
            city_id=str(row[1]),
            city_slug=str(row[2]),
            cycle_id=str(row[3]),
            status=str(row[4]),
            parser_version=str(row[5]),
            source_version=str(row[6]),
            started_at=str(row[7]) if row[7] is not None else None,
            finished_at=str(row[8]) if row[8] is not None else None,
            confidence_score=confidence_score,
        )

    @staticmethod
    def _extract_confidence_score(metadata_json: str | None) -> float | None:
        if metadata_json is None:
            return None

        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            return None

        if not isinstance(metadata, dict):
            return None

        for key in ("confidence_score", "confidence", "score"):
            score = metadata.get(key)
            if isinstance(score, bool):
                continue
            if isinstance(score, (int, float)):
                normalized = float(score)
                if 0.0 <= normalized <= 1.0:
                    return normalized
        return None
