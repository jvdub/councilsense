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


def _b64url(data: dict) -> str:
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


def _client_with_configured_cities(monkeypatch, *, secret: str, supported_city_ids: str) -> TestClient:
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


def test_city_meetings_list_returns_paginated_items_with_status_and_confidence(monkeypatch) -> None:
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids=f"{PILOT_CITY_ID},other-city",
    )
    token = _issue_token("user-list", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    set_city_response = client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID})
    assert set_city_response.status_code == 200

    _insert_meeting(
        client,
        meeting_id="meeting-c",
        meeting_uid="uid-c",
        title="Meeting C",
        created_at="2026-02-20 12:00:00",
    )
    _insert_meeting(
        client,
        meeting_id="meeting-b",
        meeting_uid="uid-b",
        title="Meeting B",
        created_at="2026-02-20 12:00:00",
    )
    _insert_meeting(
        client,
        meeting_id="meeting-a",
        meeting_uid="uid-a",
        title="Meeting A",
        created_at="2026-02-19 08:00:00",
    )

    _insert_publication(
        client,
        publication_id="pub-c-v1",
        meeting_id="meeting-c",
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        published_at="2026-02-20 13:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-b-v1",
        meeting_id="meeting-b",
        publication_status="processed",
        confidence_label="high",
        published_at="2026-02-20 12:30:00",
    )

    first_page = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params={"limit": 2})

    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["limit"] == 2
    assert [item["id"] for item in first_payload["items"]] == ["meeting-c", "meeting-b"]
    assert first_payload["items"][0]["status"] == "limited_confidence"
    assert first_payload["items"][0]["confidence_label"] == "limited_confidence"
    assert first_payload["items"][0]["reader_low_confidence"] is True
    assert first_payload["items"][1]["reader_low_confidence"] is False
    assert first_payload["next_cursor"] is not None

    second_page = client.get(
        f"/v1/cities/{PILOT_CITY_ID}/meetings",
        headers=headers,
        params={"limit": 2, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert [item["id"] for item in second_payload["items"]] == ["meeting-a"]
    assert second_payload["items"][0]["reader_low_confidence"] is False
    assert second_payload["next_cursor"] is None

    filtered = client.get(
        f"/v1/cities/{PILOT_CITY_ID}/meetings",
        headers=headers,
        params={"status": "processed", "limit": 5},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == ["meeting-b"]


def test_city_meetings_list_response_contract_includes_required_fields(monkeypatch) -> None:
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token = _issue_token("user-contract", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    set_city_response = client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID})
    assert set_city_response.status_code == 200

    _insert_meeting(
        client,
        meeting_id="meeting-contract-1",
        meeting_uid="uid-contract-1",
        title="Meeting Contract 1",
        created_at="2026-02-24 12:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-contract-1",
        meeting_id="meeting-contract-1",
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        published_at="2026-02-24 12:30:00",
    )

    response = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params={"limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"items", "next_cursor", "limit"}
    assert payload["limit"] == 1
    assert isinstance(payload["next_cursor"], str)
    assert len(payload["items"]) == 1

    item = payload["items"][0]
    assert set(item.keys()) == {
        "id",
        "city_id",
        "meeting_uid",
        "title",
        "created_at",
        "updated_at",
        "status",
        "confidence_label",
        "reader_low_confidence",
    }
    assert item["id"] == "meeting-contract-1"
    assert item["status"] == "limited_confidence"
    assert item["confidence_label"] == "limited_confidence"
    assert item["reader_low_confidence"] is True


def test_city_meetings_list_pagination_traversal_is_stable(monkeypatch) -> None:
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token = _issue_token("user-pagination", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    set_city_response = client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID})
    assert set_city_response.status_code == 200

    _insert_meeting(
        client,
        meeting_id="meeting-page-d",
        meeting_uid="uid-page-d",
        title="Meeting Page D",
        created_at="2026-02-25 09:00:00",
    )
    _insert_meeting(
        client,
        meeting_id="meeting-page-c",
        meeting_uid="uid-page-c",
        title="Meeting Page C",
        created_at="2026-02-25 09:00:00",
    )
    _insert_meeting(
        client,
        meeting_id="meeting-page-b",
        meeting_uid="uid-page-b",
        title="Meeting Page B",
        created_at="2026-02-24 09:00:00",
    )
    _insert_meeting(
        client,
        meeting_id="meeting-page-a",
        meeting_uid="uid-page-a",
        title="Meeting Page A",
        created_at="2026-02-23 09:00:00",
    )

    expected_order = ["meeting-page-d", "meeting-page-c", "meeting-page-b", "meeting-page-a"]

    seen_ids: list[str] = []
    cursor: str | None = None
    while True:
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor

        response = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params=params)
        assert response.status_code == 200
        payload = response.json()

        page_ids = [item["id"] for item in payload["items"]]
        seen_ids.extend(page_ids)
        cursor = payload["next_cursor"]
        if cursor is None:
            break

    assert seen_ids == expected_order

    replay_first_page = client.get(f"/v1/cities/{PILOT_CITY_ID}/meetings", headers=headers, params={"limit": 2})
    assert replay_first_page.status_code == 200
    replay_payload = replay_first_page.json()
    assert [item["id"] for item in replay_payload["items"]] == expected_order[:2]


def test_city_meetings_list_rejects_city_scope_bypass(monkeypatch) -> None:
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids=f"{PILOT_CITY_ID},other-city",
    )
    token = _issue_token("user-scope", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    set_city_response = client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID})
    assert set_city_response.status_code == 200

    response = client.get("/v1/cities/other-city/meetings", headers=headers)

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "forbidden",
            "message": "City access denied",
        }
    }
