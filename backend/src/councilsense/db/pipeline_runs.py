from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal


RunLifecycleStatus = Literal["pending", "processed", "failed", "limited_confidence"]


@dataclass(frozen=True)
class ProcessingRunRecord:
    id: str
    city_id: str
    cycle_id: str
    status: RunLifecycleStatus
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


class ProcessingRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_pending_run(self, *, run_id: str, city_id: str, cycle_id: str) -> ProcessingRunRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO processing_runs (id, city_id, cycle_id, status, started_at)
                VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                """,
                (run_id, city_id, cycle_id),
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
            SELECT id, city_id, cycle_id, status, started_at, finished_at
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
            started_at=str(row[4]) if row[4] is not None else None,
            finished_at=str(row[5]) if row[5] is not None else None,
        )

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


class ProcessingLifecycleService:
    def __init__(self, repository: ProcessingRunRepository) -> None:
        self._repository = repository

    def mark_processed(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="processed")

    def mark_failed(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="failed")

    def mark_limited_confidence(self, *, run_id: str) -> ProcessingRunRecord:
        return self._repository.mark_run_completed(run_id=run_id, status="limited_confidence")
