from __future__ import annotations

import sqlite3
from pathlib import Path

from councilsense.app.local_runtime import initialize_local_runtime_db, run_worker_once
from councilsense.app.meeting_processing_requests import MeetingProcessingRequestService
from councilsense.app.settings import OnDemandProcessingAdmissionControlSettings


def _stub_fetch(url: str, __: float) -> bytes:
    if "/Events/701" in url:
        return (
            '{"id":701,"agendaId":1701,"eventName":"City Council Meeting","eventDate":"2026-03-05T00:00:00Z",'
            '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":2102,"url":"stream/fixture-minutes.pdf"}]}'
        ).encode("utf-8")
    if "/events?" in url or url.endswith("/events"):
        return (
            '{"value":[{"id":701,"eventName":"City Council Meeting","eventDate":"2026-03-05T00:00:00Z",'
            '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":2102,"url":"stream/fixture-minutes.pdf"}]}]}'
        ).encode("utf-8")
    if "/Meetings/1701" in url:
        return (
            '{"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":2102,"url":"stream/fixture-minutes.pdf"}]}'
        ).encode("utf-8")
    if "GetMeetingFile(" in url and "plainText=true" in url:
        return b'{"blobUri":"https://blob.example/on-demand-minutes.txt"}'
    if "GetMeetingFile(" in url and "plainText=false" in url:
        return b'{"blobUri":"https://blob.example/on-demand-minutes.pdf"}'
    if url.endswith("on-demand-minutes.txt"):
        return b"City Council approved minutes and directed staff to publish updates."
    return b"%PDF-1.7\nmock pdf bytes"


def test_worker_once_processes_pending_on_demand_request(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "local-runtime-on-demand.db"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr("councilsense.app.local_latest_fetch._fetch_url_bytes", _stub_fetch)

    initialize_local_runtime_db(connection)
    connection.execute(
        """
        INSERT INTO discovered_meetings (
            id,
            city_id,
            city_source_id,
            provider_name,
            source_meeting_id,
            title,
            meeting_date,
            body_name,
            source_url,
            discovered_at,
            synced_at,
            meeting_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "discovered-on-demand-1",
            "city-eagle-mountain-ut",
            "source-eagle-mountain-ut-minutes-primary",
            "civicclerk",
            "701",
            "City Council Meeting",
            "2026-03-05",
            "City Council",
            "https://eaglemountainut.portal.civicclerk.com/event/701/files",
            "2026-03-10T16:00:00Z",
            "2026-03-10T16:00:00Z",
            None,
        ),
    )

    service = MeetingProcessingRequestService(
        connection=connection,
        admission_control=OnDemandProcessingAdmissionControlSettings(
            max_active_requests_per_user=5,
            max_queued_requests_per_user=3,
        ),
    )
    queued = service.queue_or_return(
        city_id="city-eagle-mountain-ut",
        discovered_meeting_id="discovered-on-demand-1",
        requested_by="local-dev-user",
    )

    assert queued.processing_status == "queued"

    result = run_worker_once(connection)

    request_row = connection.execute(
        "SELECT status, meeting_id FROM meeting_processing_requests WHERE id = ?",
        (queued.processing_request_id,),
    ).fetchone()
    run_row = connection.execute(
        "SELECT status FROM processing_runs WHERE id = ?",
        (
            connection.execute(
                "SELECT processing_run_id FROM meeting_processing_requests WHERE id = ?",
                (queued.processing_request_id,),
            ).fetchone()[0],
        ),
    ).fetchone()
    stage_row = connection.execute(
        """
        SELECT started_at, finished_at, meeting_id
        FROM processing_stage_outcomes
        WHERE run_id = (
            SELECT processing_run_id FROM meeting_processing_requests WHERE id = ?
        )
          AND stage_name = 'ingest'
        """,
        (queued.processing_request_id,),
    ).fetchone()
    publication_count = connection.execute(
        "SELECT COUNT(*) FROM summary_publications WHERE meeting_id = ?",
        (request_row[1],),
    ).fetchone()

    assert result["on_demand_claimed_count"] == 1
    assert result["on_demand_processed_count"] == 1
    assert request_row is not None and request_row[0] == "completed"
    assert request_row[1] is not None
    assert run_row is not None and run_row[0] in {"processed", "limited_confidence", "manual_review_needed"}
    assert stage_row is not None and stage_row[0] is not None and stage_row[2] == request_row[1]
    assert publication_count is not None and int(publication_count[0]) == 1