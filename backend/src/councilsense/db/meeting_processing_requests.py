from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from councilsense.db.pipeline_runs import ProcessingRunRepository


MeetingProcessingRequestStatus = Literal[
    "requested",
    "accepted",
    "processing",
    "completed",
    "failed",
    "cancelled",
]


MEETING_PROCESSING_ACTIVE_WORK_DEDUPE_KEY_VERSION = "st038-active-work-dedupe-v1"


@dataclass(frozen=True)
class MeetingProcessingRequestRecord:
    id: str
    discovered_meeting_id: str
    city_id: str
    meeting_id: str | None
    processing_run_id: str | None
    processing_stage_outcome_id: str | None
    work_dedupe_key: str | None
    attempt_number: int
    reopened_from_request_id: str | None
    status: MeetingProcessingRequestStatus
    requested_by: str
    processing_run_status: str | None
    processing_stage_started_at: str | None
    created_at: str
    updated_at: str


def build_meeting_processing_active_work_dedupe_key(
    *,
    city_id: str,
    city_source_id: str,
    provider_name: str,
    source_meeting_id: str,
) -> str:
    normalized = ":".join(
        (
            city_id.strip(),
            city_source_id.strip(),
            provider_name.strip().lower(),
            source_meeting_id.strip(),
        )
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{MEETING_PROCESSING_ACTIVE_WORK_DEDUPE_KEY_VERSION}:{digest}"


def is_active_processing_request_status(status: str) -> bool:
    return status in {"requested", "accepted", "processing"}


def is_terminal_processing_request_status(status: str) -> bool:
    return status in {"completed", "failed", "cancelled"}


class MeetingProcessingRequestRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_request_if_absent(
        self,
        *,
        request_id: str,
        discovered_meeting_id: str,
        city_id: str,
        meeting_id: str | None,
        work_dedupe_key: str,
        requested_by: str,
        lifecycle_meeting_id: str,
        stage_metadata: dict[str, object],
        attempt_number: int = 1,
        reopened_from_request_id: str | None = None,
    ) -> tuple[MeetingProcessingRequestRecord, bool]:
        normalized_meeting_id = meeting_id.strip() if isinstance(meeting_id, str) and meeting_id.strip() else None
        normalized_reopened_from_request_id = (
            reopened_from_request_id.strip()
            if isinstance(reopened_from_request_id, str) and reopened_from_request_id.strip()
            else None
        )
        normalized_work_dedupe_key = work_dedupe_key.strip()
        processing_run_id = f"run-on-demand-{uuid4().hex}"
        processing_stage_outcome_id = f"outcome-ingest-on-demand-{uuid4().hex}"
        cycle_id = f"on-demand:{request_id.strip()}"
        run_repository = ProcessingRunRepository(self._connection)
        parser_version, source_version = run_repository._derive_run_provenance(city_id=city_id.strip())
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO meeting_processing_requests (
                        id,
                        discovered_meeting_id,
                        city_id,
                        meeting_id,
                        processing_run_id,
                        processing_stage_outcome_id,
                        work_dedupe_key,
                        attempt_number,
                        reopened_from_request_id,
                        status,
                        requested_by
                    )
                    VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, 'requested', ?)
                    """,
                    (
                        request_id.strip(),
                        discovered_meeting_id.strip(),
                        city_id.strip(),
                        normalized_meeting_id,
                        normalized_work_dedupe_key,
                        attempt_number,
                        normalized_reopened_from_request_id,
                        requested_by.strip(),
                    ),
                )
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
                    (
                        processing_run_id,
                        city_id.strip(),
                        cycle_id,
                        parser_version,
                        source_version,
                    ),
                )
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
                    VALUES (?, ?, ?, ?, 'ingest', 'pending', ?, NULL, NULL)
                    """,
                    (
                        processing_stage_outcome_id,
                        processing_run_id,
                        city_id.strip(),
                        lifecycle_meeting_id.strip(),
                        json.dumps(stage_metadata, sort_keys=True, separators=(",", ":")),
                    ),
                )
                self._connection.execute(
                    """
                    UPDATE meeting_processing_requests
                    SET
                        processing_run_id = ?,
                        processing_stage_outcome_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (processing_run_id, processing_stage_outcome_id, request_id.strip()),
                )
        except sqlite3.IntegrityError:
            existing = self.get_active_for_work_dedupe_key(work_dedupe_key=normalized_work_dedupe_key)
            if existing is None:
                existing = self.get_active_for_discovered(discovered_meeting_id=discovered_meeting_id)
            if existing is None:
                raise
            return existing, False

        created = self.get_request(request_id=request_id)
        assert created is not None
        return created, True

    def get_request(self, *, request_id: str) -> MeetingProcessingRequestRecord | None:
        row = self._connection.execute(
            """
            SELECT
                req.id,
                req.discovered_meeting_id,
                req.city_id,
                req.meeting_id,
                req.processing_run_id,
                req.processing_stage_outcome_id,
                req.work_dedupe_key,
                req.attempt_number,
                req.reopened_from_request_id,
                req.status,
                req.requested_by,
                pr.status,
                pso.started_at,
                req.created_at,
                req.updated_at
            FROM meeting_processing_requests req
            LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = req.processing_stage_outcome_id
            WHERE req.id = ?
            """,
            (request_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        return _to_processing_request_record(row)

    def get_active_for_discovered(self, *, discovered_meeting_id: str) -> MeetingProcessingRequestRecord | None:
        row = self._connection.execute(
            """
            SELECT
                                req.id,
                                req.discovered_meeting_id,
                                req.city_id,
                                req.meeting_id,
                                req.processing_run_id,
                                req.processing_stage_outcome_id,
                                req.work_dedupe_key,
                                req.attempt_number,
                                req.reopened_from_request_id,
                                req.status,
                                req.requested_by,
                                pr.status,
                                pso.started_at,
                                req.created_at,
                                req.updated_at
                        FROM meeting_processing_requests req
                        LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
                        LEFT JOIN processing_stage_outcomes pso ON pso.id = req.processing_stage_outcome_id
                        WHERE req.discovered_meeting_id = ?
                            AND (
                                        (req.processing_run_id IS NOT NULL AND pr.status = 'pending')
                                 OR (req.processing_run_id IS NULL AND req.status IN ('requested', 'accepted', 'processing'))
                            )
                        ORDER BY req.created_at DESC, req.id DESC
            LIMIT 1
            """,
            (discovered_meeting_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        return _to_processing_request_record(row)

    def get_active_for_work_dedupe_key(self, *, work_dedupe_key: str) -> MeetingProcessingRequestRecord | None:
        row = self._connection.execute(
            """
            SELECT
                req.id,
                req.discovered_meeting_id,
                req.city_id,
                req.meeting_id,
                req.processing_run_id,
                req.processing_stage_outcome_id,
                req.work_dedupe_key,
                req.attempt_number,
                req.reopened_from_request_id,
                req.status,
                req.requested_by,
                pr.status,
                pso.started_at,
                req.created_at,
                req.updated_at
            FROM meeting_processing_requests req
            LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = req.processing_stage_outcome_id
            WHERE req.work_dedupe_key = ?
              AND (
                    (req.processing_run_id IS NOT NULL AND pr.status = 'pending')
                 OR (req.processing_run_id IS NULL AND req.status IN ('requested', 'accepted', 'processing'))
              )
            ORDER BY req.created_at DESC, req.id DESC
            LIMIT 1
            """,
            (work_dedupe_key.strip(),),
        ).fetchone()
        if row is None:
            return None
        return _to_processing_request_record(row)

    def get_latest_for_discovered(self, *, discovered_meeting_id: str) -> MeetingProcessingRequestRecord | None:
        row = self._connection.execute(
            """
            SELECT
                req.id,
                req.discovered_meeting_id,
                req.city_id,
                req.meeting_id,
                req.processing_run_id,
                req.processing_stage_outcome_id,
                req.work_dedupe_key,
                req.attempt_number,
                req.reopened_from_request_id,
                req.status,
                req.requested_by,
                pr.status,
                pso.started_at,
                req.created_at,
                req.updated_at
            FROM meeting_processing_requests req
            LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = req.processing_stage_outcome_id
            WHERE req.discovered_meeting_id = ?
            ORDER BY req.created_at DESC, req.id DESC
            LIMIT 1
            """,
            (discovered_meeting_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        return _to_processing_request_record(row)

    def count_active_for_requested_by(self, *, requested_by: str) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM meeting_processing_requests req
            LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
            WHERE req.requested_by = ?
              AND (
                    (req.processing_run_id IS NOT NULL AND pr.status = 'pending')
                 OR (req.processing_run_id IS NULL AND req.status IN ('requested', 'accepted', 'processing'))
              )
            """,
            (requested_by.strip(),),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def count_queued_for_requested_by(self, *, requested_by: str) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM meeting_processing_requests req
            LEFT JOIN processing_runs pr ON pr.id = req.processing_run_id
            LEFT JOIN processing_stage_outcomes pso ON pso.id = req.processing_stage_outcome_id
            WHERE req.requested_by = ?
              AND (
                    (req.processing_run_id IS NOT NULL AND pr.status = 'pending' AND pso.started_at IS NULL)
                 OR (req.processing_run_id IS NULL AND req.status IN ('requested', 'accepted'))
              )
            """,
            (requested_by.strip(),),
        ).fetchone()
        return int(row[0]) if row is not None else 0


def _to_processing_request_record(row: sqlite3.Row | tuple[object, ...]) -> MeetingProcessingRequestRecord:
    return MeetingProcessingRequestRecord(
        id=str(row[0]),
        discovered_meeting_id=str(row[1]),
        city_id=str(row[2]),
        meeting_id=str(row[3]) if row[3] is not None else None,
        processing_run_id=str(row[4]) if row[4] is not None else None,
        processing_stage_outcome_id=str(row[5]) if row[5] is not None else None,
        work_dedupe_key=str(row[6]) if row[6] is not None else None,
        attempt_number=int(row[7]),
        reopened_from_request_id=str(row[8]) if row[8] is not None else None,
        status=str(row[9]),
        requested_by=str(row[10]),
        processing_run_status=str(row[11]) if row[11] is not None else None,
        processing_stage_started_at=str(row[12]) if row[12] is not None else None,
        created_at=str(row[13]),
        updated_at=str(row[14]),
    )