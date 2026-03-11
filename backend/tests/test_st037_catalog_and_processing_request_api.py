from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID


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


def _client(monkeypatch, *, secret: str, supported_city_ids: str) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    monkeypatch.setenv("SUPPORTED_CITY_IDS", supported_city_ids)
    return TestClient(create_app())


def _insert_meeting(
    client: TestClient,
    *,
    meeting_id: str,
    meeting_uid: str,
    title: str,
    created_at: str,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, meeting_uid, title, created_at, created_at),
    )


def _insert_publication(
    client: TestClient,
    *,
    publication_id: str,
    meeting_id: str,
    publication_status: str,
    confidence_label: str,
    published_at: str,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO summary_publications (
            id,
            meeting_id,
            processing_run_id,
            publish_stage_outcome_id,
            version_no,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            meeting_id,
            None,
            None,
            1,
            publication_status,
            confidence_label,
            "Summary",
            "[]",
            "[]",
            "[]",
            published_at,
            published_at,
        ),
    )


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


def _insert_processing_request(
    client: TestClient,
    *,
    request_id: str,
    discovered_meeting_id: str,
    status: str,
    updated_at: str,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO meeting_processing_requests (
            id,
            discovered_meeting_id,
            city_id,
            meeting_id,
            status,
            requested_by,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            request_id,
            discovered_meeting_id,
            PILOT_CITY_ID,
            status,
            "user-test",
            updated_at,
            updated_at,
        ),
    )


def test_city_meetings_list_includes_discovered_and_processed_rows(monkeypatch) -> None:
    client = _client(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-catalog", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200

    _insert_meeting(
        client,
        meeting_id="meeting-processed",
        meeting_uid="uid-processed",
        title="Processed Meeting",
        created_at="2026-03-10 08:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-processed",
        meeting_id="meeting-processed",
        publication_status="processed",
        confidence_label="high",
        published_at="2026-03-10 09:00:00",
    )
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-upcoming",
        source_meeting_id="71",
        title="Upcoming Meeting",
        meeting_date="2026-03-20",
        discovered_at="2026-03-11T09:00:00Z",
        synced_at="2026-03-11T09:00:00Z",
    )
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-linked",
        source_meeting_id="72",
        title="Processed Meeting",
        meeting_date="2026-03-10",
        discovered_at="2026-03-10T08:00:00Z",
        synced_at="2026-03-10T08:00:00Z",
        meeting_id="meeting-processed",
    )

    response = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == ["discovered-upcoming", "discovered-linked"]
    assert payload["items"][0]["processing"]["processing_status"] == "discovered"
    assert payload["items"][0]["meeting_id"] is None
    assert payload["items"][0]["detail_available"] is False
    assert payload["items"][1]["meeting_id"] == "meeting-processed"
    assert payload["items"][1]["status"] == "processed"
    assert payload["items"][1]["processing"]["processing_status"] == "processed"


def test_city_meetings_list_projects_active_and_failed_request_statuses(monkeypatch) -> None:
    client = _client(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-active", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200

    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-queued",
        source_meeting_id="81",
        title="Queued Meeting",
        meeting_date="2026-03-18",
        discovered_at="2026-03-11T08:00:00Z",
        synced_at="2026-03-11T08:00:00Z",
    )
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-failed",
        source_meeting_id="82",
        title="Failed Meeting",
        meeting_date="2026-03-17",
        discovered_at="2026-03-11T07:00:00Z",
        synced_at="2026-03-11T07:00:00Z",
    )
    _insert_processing_request(
        client,
        request_id="request-queued",
        discovered_meeting_id="discovered-queued",
        status="requested",
        updated_at="2026-03-11T08:05:00Z",
    )
    _insert_processing_request(
        client,
        request_id="request-failed",
        discovered_meeting_id="discovered-failed",
        status="failed",
        updated_at="2026-03-11T07:05:00Z",
    )

    response = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["processing"]["processing_status"] for item in payload["items"]] == ["queued", "failed"]
    assert payload["items"][0]["processing"]["processing_request_id"] == "request-queued"

    filtered = client.get(
        f"/v1/cities/{PILOT_CITY_ID}/meetings",
        headers=headers,
        params={"limit": 10, "status": "queued"},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == ["discovered-queued"]


def test_processing_request_endpoint_returns_created_then_existing_active(monkeypatch) -> None:
    client = _client(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-request", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-request",
        source_meeting_id="91",
        title="Requestable Meeting",
        meeting_date="2026-03-19",
        discovered_at="2026-03-11T10:00:00Z",
        synced_at="2026-03-11T10:00:00Z",
    )

    first = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-request/processing-request",
        headers=headers,
    )
    second = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-request/processing-request",
        headers=headers,
    )

    assert first.status_code == 201
    assert first.json()["processing"]["request_outcome"] == "queued"
    assert first.json()["processing"]["processing_status"] == "queued"
    assert second.status_code == 200
    assert second.json()["processing"]["request_outcome"] == "already_active"
    assert second.json()["processing"]["processing_request_id"] == first.json()["processing"]["processing_request_id"]


def test_processing_request_endpoint_rejects_other_city_and_processed_meetings(monkeypatch) -> None:
    client = _client(monkeypatch, secret="test-secret", supported_city_ids=f"{PILOT_CITY_ID},other-city")
    token = _issue_token("user-request-scope", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID}).status_code == 200
    _insert_meeting(
        client,
        meeting_id="meeting-already-processed",
        meeting_uid="uid-already-processed",
        title="Already Processed",
        created_at="2026-03-10 08:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-already-processed",
        meeting_id="meeting-already-processed",
        publication_status="processed",
        confidence_label="high",
        published_at="2026-03-10 09:00:00",
    )
    _insert_discovered_meeting(
        client,
        discovered_meeting_id="discovered-already-processed",
        source_meeting_id="99",
        title="Already Processed",
        meeting_date="2026-03-10",
        discovered_at="2026-03-10T08:00:00Z",
        synced_at="2026-03-10T08:00:00Z",
        meeting_id="meeting-already-processed",
    )

    forbidden = client.post(
        "/v1/cities/other-city/meetings/discovered-already-processed/processing-request",
        headers=headers,
    )
    processed = client.post(
        f"/v1/cities/{PILOT_CITY_ID}/meetings/discovered-already-processed/processing-request",
        headers=headers,
    )

    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "error": {
            "code": "forbidden",
            "message": "City access denied",
        }
    }
    assert processed.status_code == 409
    assert processed.json() == {"detail": "Meeting already processed"}