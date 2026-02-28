from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import sqlite3
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.governance_exports import GovernanceExportProcessor, GovernanceExportService
from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID, apply_migrations


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


def _insert_meeting(client: TestClient, *, meeting_id: str) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, f"uid-{meeting_id}", "City Council Meeting"),
    )


def _insert_notification_history(client: TestClient, *, user_id: str, meeting_id: str) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO notification_outbox (
            id,
            user_id,
            meeting_id,
            city_id,
            notification_type,
            dedupe_key,
            payload_json,
            status,
            attempt_count,
            max_attempts,
            next_retry_at,
            subscription_id,
            sent_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "outbox-export-1",
            user_id,
            meeting_id,
            PILOT_CITY_ID,
            "meeting_published",
            f"dedupe-{user_id}-{meeting_id}",
            '{"event":"meeting_published"}',
            "sent",
            1,
            3,
            "2026-02-28T10:00:00+00:00",
            "sub-123",
            "2026-02-28T10:01:00+00:00",
        ),
    )
    app.state.db_connection.execute(
        """
        INSERT INTO notification_delivery_attempts (
            outbox_id,
            attempt_number,
            outcome,
            attempted_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "outbox-export-1",
            1,
            "success",
            "2026-02-28T10:01:00+00:00",
            "2026-02-28T10:01:00+00:00",
        ),
    )


def test_export_request_processing_and_artifact_download(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-export-1", secret="test-secret", expires_in_seconds=600)
    headers = {"Authorization": f"Bearer {token}"}

    set_profile = client.patch(
        "/v1/me",
        headers=headers,
        json={
            "home_city_id": PILOT_CITY_ID,
            "notifications_enabled": False,
            "notifications_paused_until": "2026-03-01T12:00:00+00:00",
        },
    )
    assert set_profile.status_code == 200

    _insert_meeting(client, meeting_id="meeting-export-1")
    _insert_notification_history(client, user_id="user-export-1", meeting_id="meeting-export-1")

    create_response = client.post(
        "/v1/me/exports",
        headers=headers,
        json={"idempotency_key": "idem-export-1"},
    )
    assert create_response.status_code == 201
    request_payload = create_response.json()
    request_id = str(request_payload["id"])
    assert request_payload["status"] == "requested"

    app = cast(Any, client.app)
    processing_result = app.state.governance_export_processor.run_once()
    assert processing_result.claimed_count == 1
    assert processing_result.completed_count == 1

    status_response = client.get(f"/v1/me/exports/{request_id}", headers=headers)
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["artifact_uri"] == f"governance-export://{request_id}"

    artifact_response = client.get(f"/v1/me/exports/{request_id}/artifact", headers=headers)
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["artifact_uri"] == f"governance-export://{request_id}"
    assert artifact_payload["schema_version"] == "2026-02-28"
    assert artifact_payload["generated_at"] is not None


def test_export_artifact_contract_includes_required_domains_and_provenance(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-export-contract", secret="test-secret", expires_in_seconds=600)
    headers = {"Authorization": f"Bearer {token}"}

    client.patch(
        "/v1/me",
        headers=headers,
        json={
            "home_city_id": PILOT_CITY_ID,
            "notifications_enabled": True,
            "notifications_paused_until": None,
        },
    )

    _insert_meeting(client, meeting_id="meeting-export-contract")
    _insert_notification_history(client, user_id="user-export-contract", meeting_id="meeting-export-contract")

    request_response = client.post(
        "/v1/me/exports",
        headers=headers,
        json={"idempotency_key": "idem-export-contract"},
    )
    request_id = str(request_response.json()["id"])

    app = cast(Any, client.app)
    app.state.governance_export_processor.run_once()

    artifact_response = client.get(f"/v1/me/exports/{request_id}/artifact", headers=headers)
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()["export"]

    assert artifact["schema_version"] == "2026-02-28"
    assert artifact["generated_at"]

    sections = artifact["sections"]
    assert set(sections.keys()) == {"profile", "preferences", "notification_history"}

    profile_section = sections["profile"]
    assert profile_section["provenance"]["source"] == "profile_service"
    assert profile_section["provenance"]["redaction_policy"] == "allowlist-v1"
    assert profile_section["data"]["user_id"] == "user-export-contract"
    assert profile_section["data"]["home_city_id"] == PILOT_CITY_ID

    preferences_section = sections["preferences"]
    assert preferences_section["provenance"]["source"] == "profile_service"
    assert preferences_section["data"]["notifications_enabled"] is True
    assert preferences_section["data"]["notifications_paused_until"] is None

    notification_history = sections["notification_history"]
    assert notification_history["provenance"]["source"] == "notification_outbox_and_attempts"
    assert isinstance(notification_history["data"], list)
    assert len(notification_history["data"]) == 1
    history_item = notification_history["data"][0]
    assert history_item["notification_id"] == "outbox-export-1"
    assert history_item["meeting_id"] == "meeting-export-contract"
    assert history_item["status"] == "sent"
    assert history_item["attempt_count"] == 1
    assert history_item["attempts"] == [
        {
            "attempt_number": 1,
            "outcome": "success",
            "attempted_at": "2026-02-28T10:01:00+00:00",
        }
    ]


def test_export_processor_retries_and_reaches_terminal_failure_state() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection)

        class _FailingProfileService:
            def get_profile(self, user_id: str) -> Any:
                raise RuntimeError(f"profile lookup failed for {user_id}")

        service = GovernanceExportService(connection=connection)
        created = service.create_request(
            user_id="user-export-failure",
            idempotency_key="idem-export-failure",
            requested_by="user-export-failure",
        )

        processor = GovernanceExportProcessor(
            connection=connection,
            profile_service=_FailingProfileService(),
        )

        first = processor.run_once()
        assert first.failed_count == 1

        second = processor.run_once()
        assert second.failed_count == 1

        third = processor.run_once()
        assert third.terminal_count == 1

        row = connection.execute(
            """
            SELECT status, error_code, processing_attempt_count, max_processing_attempts
            FROM governance_export_requests
            WHERE id = ?
            """,
            (created.id,),
        ).fetchone()
        assert row == ("cancelled", "export_generation_failed_terminal", 3, 3)
    finally:
        connection.close()
