from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from councilsense.app.settings import OnDemandProcessingAdmissionControlSettings
from councilsense.db import DiscoveredMeetingRepository, MeetingProcessingRequestRepository, MeetingReadRepository
from councilsense.db.meeting_processing_requests import build_meeting_processing_active_work_dedupe_key


class MeetingProcessingRequestNotFoundError(Exception):
    pass


class MeetingProcessingRequestAlreadyProcessedError(Exception):
    pass


class MeetingProcessingRequestAdmissionControlError(Exception):
    def __init__(self, *, reason: str, limit: int, current_count: int) -> None:
        self.reason = reason
        self.limit = limit
        self.current_count = current_count
        super().__init__(reason)


@dataclass(frozen=True)
class MeetingProcessingQueueOrReturnResult:
    discovered_meeting_id: str
    city_id: str
    meeting_id: str | None
    processing_request_id: str
    processing_status: str
    processing_status_updated_at: str
    request_outcome: str


class MeetingProcessingRequestService:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        admission_control: OnDemandProcessingAdmissionControlSettings,
    ) -> None:
        self._connection = connection
        self._admission_control = admission_control
        self._discovered_repository = DiscoveredMeetingRepository(connection)
        self._request_repository = MeetingProcessingRequestRepository(connection)
        self._meeting_read_repository = MeetingReadRepository(connection)

    def queue_or_return(
        self,
        *,
        city_id: str,
        discovered_meeting_id: str,
        requested_by: str,
    ) -> MeetingProcessingQueueOrReturnResult:
        discovered = self._discovered_repository.get_by_id(discovered_meeting_id=discovered_meeting_id)
        if discovered is None:
            raise MeetingProcessingRequestNotFoundError()
        if discovered.city_id != city_id.strip():
            raise MeetingProcessingRequestNotFoundError()

        if discovered.meeting_id is not None:
            detail = self._meeting_read_repository.get_meeting_detail_for_city(
                meeting_id=discovered.meeting_id,
                city_id=discovered.city_id,
            )
            if detail is not None and detail.publication_status is not None:
                raise MeetingProcessingRequestAlreadyProcessedError()

        work_dedupe_key = build_meeting_processing_active_work_dedupe_key(
            city_id=discovered.city_id,
            city_source_id=discovered.city_source_id,
            provider_name=discovered.provider_name,
            source_meeting_id=discovered.source_meeting_id,
        )
        existing_active = self._request_repository.get_active_for_work_dedupe_key(work_dedupe_key=work_dedupe_key)
        if existing_active is not None:
            return MeetingProcessingQueueOrReturnResult(
                discovered_meeting_id=discovered.id,
                city_id=discovered.city_id,
                meeting_id=discovered.meeting_id,
                processing_request_id=existing_active.id,
                processing_status=_user_visible_processing_status(existing_active),
                processing_status_updated_at=(
                    existing_active.processing_stage_started_at or existing_active.updated_at
                ),
                request_outcome="already_active",
            )

        active_count = self._request_repository.count_active_for_requested_by(requested_by=requested_by)
        if active_count >= self._admission_control.max_active_requests_per_user:
            raise MeetingProcessingRequestAdmissionControlError(
                reason="active_limit_exceeded",
                limit=self._admission_control.max_active_requests_per_user,
                current_count=active_count,
            )

        queued_count = self._request_repository.count_queued_for_requested_by(requested_by=requested_by)
        if queued_count >= self._admission_control.max_queued_requests_per_user:
            raise MeetingProcessingRequestAdmissionControlError(
                reason="queued_limit_exceeded",
                limit=self._admission_control.max_queued_requests_per_user,
                current_count=queued_count,
            )

        latest = self._request_repository.get_latest_for_discovered(discovered_meeting_id=discovered.id)
        attempt_number = (latest.attempt_number + 1) if latest is not None else 1
        reopened_from_request_id = latest.id if latest is not None and latest.status in {"failed", "cancelled", "completed"} else None

        record, created = self._request_repository.create_request_if_absent(
            request_id=f"mpr-{uuid4().hex}",
            discovered_meeting_id=discovered.id,
            city_id=discovered.city_id,
            meeting_id=discovered.meeting_id,
            work_dedupe_key=work_dedupe_key,
            requested_by=requested_by,
            lifecycle_meeting_id=discovered.meeting_id or discovered.id,
            stage_metadata={
                "attempt_number": attempt_number,
                "discovered_meeting_id": discovered.id,
                "requested_by": requested_by,
                "reopened_from_request_id": reopened_from_request_id,
                "trigger": "resident_on_demand",
                "work_dedupe_key": work_dedupe_key,
            },
            attempt_number=attempt_number,
            reopened_from_request_id=reopened_from_request_id,
        )
        return MeetingProcessingQueueOrReturnResult(
            discovered_meeting_id=discovered.id,
            city_id=discovered.city_id,
            meeting_id=discovered.meeting_id,
            processing_request_id=record.id,
            processing_status=_user_visible_processing_status(record),
            processing_status_updated_at=(record.processing_stage_started_at or record.updated_at),
            request_outcome="queued" if created else "already_active",
        )


def _user_visible_processing_status(record) -> str:
    if record.processing_run_status == "pending":
        if record.processing_stage_started_at is not None:
            return "processing"
        return "queued"
    if record.status in {"requested", "accepted"}:
        return "queued"
    if record.status == "processing":
        return "processing"
    if record.status in {"failed", "cancelled"}:
        return "failed"
    if record.status == "completed":
        return "processed"
    if record.processing_run_status in {"failed", "processed", "limited_confidence", "manual_review_needed"}:
        return "failed"
    return "queued"