from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.db import (
    MEETING_PROCESSING_ACTIVE_WORK_DEDUPE_KEY_VERSION,
    MeetingProcessingRequestRepository,
    PILOT_CITY_ID,
    build_meeting_processing_active_work_dedupe_key,
    is_active_processing_request_status,
    is_terminal_processing_request_status,
)


def _b64url(data: dict[str, object]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _issue_token(user_id: str, *, secret: str, expires_in_seconds: int) -> str:
    header = _b64url({"alg": "HS256", "typ": "JWT"})
    exp = int((datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)).timestamp())
    payload = _b64url({"sub": user_id, "exp": exp})
    signing_input = f"{header}.{payload}"
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return f"{signing_input}.{signature}"


def _client(
    monkeypatch,
    *,
    secret: str,
    supported_city_ids: str,
    active_limit: int = 5,
    queued_limit: int = 3,
) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    monkeypatch.setenv("SUPPORTED_CITY_IDS", supported_city_ids)
    monkeypatch.setenv("ON_DEMAND_PROCESSING_ACTIVE_REQUESTS_PER_USER_LIMIT", str(active_limit))
    monkeypatch.setenv("ON_DEMAND_PROCESSING_QUEUED_REQUESTS_PER_USER_LIMIT", str(queued_limit))
    return TestClient(create_app())


def _insert_discovered_meeting(
    client: TestClient,
    *,
    discovered_meeting_id: str,
    source_meeting_id: str,
    title: str,
    meeting_date: str,
    discovered_at: str,
    synced_at: str,
    meeting_id: str | None = None,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
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
            discovered_meeting_id,
            PILOT_CITY_ID,
            "source-eagle-mountain-ut-minutes-primary",
            "civicclerk",
            source_meeting_id,
            title,
            meeting_date,
            "City Council",
            f"https://eaglemountainut.portal.civicclerk.com/event/{source_meeting_id}/files",
            discovered_at,
            synced_at,
            meeting_id,
        ),
    )


def _request_headers(*, user_id: str, secret: str) -> dict[str, str]:
    token = _issue_token(user_id, secret=secret, expires_in_seconds=300)
    return {"Authorization": f"Bearer {token}"}


def test_active_work_dedupe_key_contract_is_stable() -> None:
    stable_one = build_meeting_processing_active_work_dedupe_key(
        city_id="city-eagle-mountain-ut",
        city_source_id="source-1",
        provider_name="CivicClerk",
        source_meeting_id="72",
    )
    stable_two = build_meeting_processing_active_work_dedupe_key(
        city_id="city-eagle-mountain-ut",
        city_source_id="source-1",
        provider_name="civicclerk",
        source_meeting_id="72",
    )
    different = build_meeting_processing_active_work_dedupe_key(
        city_id="city-eagle-mountain-ut",
        city_source_id="source-1",
        provider_name="civicclerk",
        source_meeting_id="73",
    )

    assert stable_one == stable_two
    assert stable_one.startswith(f"{MEETING_PROCESSING_ACTIVE_WORK_DEDUPE_KEY_VERSION}:")
    assert different != stable_one
    assert is_active_processing_request_status("requested") is True
    assert is_active_processing_request_status("processing") is True
    assert is_terminal_processing_request_status("failed") is True
    assert is_terminal_processing_request_status("cancelled") is True


def test_duplicate_click_reuses_active_work_before_limit_rejection(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, supported_city_ids=PILOT_CITY_ID, active_limit=1, queued_limit=1)
    headers = _request_headers(user_id="user-dedupe", secret=secret)

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-a",
        source_meeting_id="101",
        title="Meeting A",
        meeting_date="2026-03-19",
        discovered_at="2026-03-11T10:00:00Z",
        synced_at="2026-03-11T10:00:00Z",
    )
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-b",
        source_meeting_id="102",
        title="Meeting B",
        meeting_date="2026-03-20",
        discovered_at="2026-03-11T10:01:00Z",
        synced_at="2026-03-11T10:01:00Z",
    )

    first = client.post(f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-a/processing-request", headers=headers)
    duplicate = client.post(f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-a/processing-request", headers=headers)
    rejected = client.post(f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-b/processing-request", headers=headers)

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["processing"]["request_outcome"] == "already_active"
    assert duplicate.json()["processing"]["processing_request_id"] == first.json()["processing"]["processing_request_id"]
    assert rejected.status_code == 429
    assert rejected.json() == {"detail": "Too many active on-demand processing requests for user"}

    app = cast(Any, client.app)
    request_count = app.state.db_connection.execute(
        "SELECT COUNT(*) FROM meeting_processing_requests"
    ).fetchone()
    run_count = app.state.db_connection.execute("SELECT COUNT(*) FROM processing_runs").fetchone()
    stage_count = app.state.db_connection.execute("SELECT COUNT(*) FROM processing_stage_outcomes").fetchone()
    assert request_count is not None and int(request_count[0]) == 1
    assert run_count is not None and int(run_count[0]) == 1
    assert stage_count is not None and int(stage_count[0]) == 1


def test_duplicate_click_projects_processing_when_active_stage_has_started(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, supported_city_ids=PILOT_CITY_ID)
    headers = _request_headers(user_id="user-processing", secret=secret)

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-processing",
        source_meeting_id="201",
        title="Processing Meeting",
        meeting_date="2026-03-22",
        discovered_at="2026-03-11T12:00:00Z",
        synced_at="2026-03-11T12:00:00Z",
    )

    created = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-processing/processing-request",
        headers=headers,
    )
    assert created.status_code == 201

    app = cast(Any, client.app)
    repository = MeetingProcessingRequestRepository(app.state.db_connection)
    request_record = repository.get_request(request_id=created.json()["processing"]["processing_request_id"])
    assert request_record is not None
    app.state.db_connection.execute(
        """
        UPDATE processing_stage_outcomes
        SET started_at = ?, updated_at = ?
        WHERE id = ?
        """,
        ("2026-03-11T12:05:00Z", "2026-03-11T12:05:00Z", request_record.processing_stage_outcome_id),
    )

    duplicate = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-processing/processing-request",
        headers=headers,
    )
    listed = client.get(
        f"/v1/cities/{PILOT_CITY_ID}/meetings",
        headers=headers,
        params={"status": "processing", "limit": 10},
    )

    assert duplicate.status_code == 200
    assert duplicate.json()["processing"]["request_outcome"] == "already_active"
    assert duplicate.json()["processing"]["processing_status"] == "processing"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == ["discovered-processing"]
    assert listed.json()["items"][0]["processing"]["processing_status"] == "processing"


def test_failed_terminal_request_can_open_new_attempt_with_lineage(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, supported_city_ids=PILOT_CITY_ID)
    headers = _request_headers(user_id="user-reopen", secret=secret)

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-reopen",
        source_meeting_id="301",
        title="Retryable Meeting",
        meeting_date="2026-03-23",
        discovered_at="2026-03-11T13:00:00Z",
        synced_at="2026-03-11T13:00:00Z",
    )

    first = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-reopen/processing-request",
        headers=headers,
    )
    assert first.status_code == 201

    app = cast(Any, client.app)
    repository = MeetingProcessingRequestRepository(app.state.db_connection)
    first_record = repository.get_request(request_id=first.json()["processing"]["processing_request_id"])
    assert first_record is not None
    app.state.db_connection.execute(
        "UPDATE processing_runs SET status = 'failed', finished_at = ?, updated_at = ? WHERE id = ?",
        ("2026-03-11T13:10:00Z", "2026-03-11T13:10:00Z", first_record.processing_run_id),
    )
    app.state.db_connection.execute(
        "UPDATE meeting_processing_requests SET status = 'failed', updated_at = ? WHERE id = ?",
        ("2026-03-11T13:10:00Z", first_record.id),
    )

    second = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-reopen/processing-request",
        headers=headers,
    )

    assert second.status_code == 201
    second_record = repository.get_request(request_id=second.json()["processing"]["processing_request_id"])
    assert second_record is not None
    assert second_record.id != first_record.id
    assert second_record.attempt_number == 2
    assert second_record.reopened_from_request_id == first_record.id
    assert second_record.work_dedupe_key == first_record.work_dedupe_key
    assert second_record.processing_run_id != first_record.processing_run_id

    active_count = app.state.db_connection.execute(
        "SELECT COUNT(*) FROM meeting_processing_requests WHERE status IN ('requested', 'accepted', 'processing')"
    ).fetchone()
    assert active_count is not None and int(active_count[0]) == 1