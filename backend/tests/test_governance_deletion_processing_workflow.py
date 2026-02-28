from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import sqlite3
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.api.profile import InMemoryUserProfileRepository, UserProfileService
from councilsense.app.governance_deletions import (
    ACTOR_PROCESSOR,
    DELETION_SLA_DAYS,
    GovernanceDeletionProcessor,
    GovernanceDeletionService,
)
from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


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


def _insert_notification_history(client: TestClient, *, user_id: str, meeting_id: str, outbox_id: str) -> None:
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
            outbox_id,
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


def _insert_summary_publication(client: TestClient, *, publication_id: str, meeting_id: str) -> None:
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
            "processed",
            "high",
            "Published summary text",
            "[]",
            "[]",
            "[]",
            "2026-02-28T10:00:00+00:00",
            "2026-02-28T10:00:00+00:00",
        ),
    )


def test_deletion_processing_removes_personal_data_and_preserves_published_provenance(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-delete-1", secret="test-secret", expires_in_seconds=600)
    headers = {"Authorization": f"Bearer {token}"}

    set_profile = client.patch(
        "/v1/me",
        headers=headers,
        json={
            "home_city_id": PILOT_CITY_ID,
            "notifications_enabled": True,
            "notifications_paused_until": "2026-03-01T12:00:00+00:00",
        },
    )
    assert set_profile.status_code == 200

    _insert_meeting(client, meeting_id="meeting-delete-1")
    _insert_notification_history(
        client,
        user_id="user-delete-1",
        meeting_id="meeting-delete-1",
        outbox_id="outbox-delete-1",
    )
    _insert_summary_publication(
        client,
        publication_id="publication-delete-1",
        meeting_id="meeting-delete-1",
    )

    create_response = client.post(
        "/v1/me/deletions",
        headers=headers,
        json={
            "idempotency_key": "idem-delete-1",
            "mode": "delete",
            "reason_code": "user_requested_account_deletion",
        },
    )
    assert create_response.status_code == 201
    request_id = str(create_response.json()["id"])

    app = cast(Any, client.app)
    result = app.state.governance_deletion_processor.run_once()
    assert result.claimed_count == 1
    assert result.completed_count == 1

    status_response = client.get(f"/v1/me/deletions/{request_id}", headers=headers)
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["due_at"] is not None
    assert status_payload["completed_at"] is not None

    profile_response = client.get("/v1/me", headers=headers)
    assert profile_response.status_code == 200
    profile_payload = profile_response.json()
    assert profile_payload["home_city_id"] is None
    assert profile_payload["notifications_enabled"] is False
    assert profile_payload["notifications_paused_until"] is None

    outbox_count = app.state.db_connection.execute(
        "SELECT COUNT(*) FROM notification_outbox WHERE user_id = ?",
        ("user-delete-1",),
    ).fetchone()
    assert outbox_count == (0,)

    publication_count = app.state.db_connection.execute(
        "SELECT COUNT(*) FROM summary_publications WHERE id = ?",
        ("publication-delete-1",),
    ).fetchone()
    assert publication_count == (1,)

    phase_rows = app.state.db_connection.execute(
        """
        SELECT metadata_json
        FROM governance_audit_events
        WHERE entity_type = 'governance_deletion_request'
          AND entity_id = ?
          AND actor_user_id = ?
        ORDER BY id ASC
        """,
        (request_id, ACTOR_PROCESSOR),
    ).fetchall()
    phases = {
        metadata["processing_phase"]
        for row in phase_rows
        for metadata in [json.loads(str(row[0]))]
        if "processing_phase" in metadata
    }
    assert phases == {"before_processing", "after_processing"}



def test_deletion_processing_sets_deterministic_sla_due_at_and_anonymizes_notification_rows() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection)
        seed_city_registry(connection)

        connection.execute(
            """
            INSERT INTO meetings (id, city_id, meeting_uid, title)
            VALUES (?, ?, ?, ?)
            """,
            ("meeting-anon-1", PILOT_CITY_ID, "uid-meeting-anon-1", "City Council Meeting"),
        )
        connection.execute(
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
                subscription_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "outbox-anon-1",
                "user-anon-1",
                "meeting-anon-1",
                PILOT_CITY_ID,
                "meeting_published",
                "dedupe-user-anon-1-meeting-anon-1",
                '{"event":"meeting_published"}',
                "sent",
                1,
                3,
                "2026-02-28T10:00:00+00:00",
                "sub-keep-private",
            ),
        )

        repository = InMemoryUserProfileRepository()
        profile_service = UserProfileService(
            repository=repository,
            supported_city_ids=(PILOT_CITY_ID,),
        )
        profile_service.patch_profile(
            "user-anon-1",
            home_city_id=PILOT_CITY_ID,
            notifications_enabled=True,
            notifications_paused_until=datetime.fromisoformat("2026-03-01T12:00:00+00:00"),
        )

        service = GovernanceDeletionService(connection=connection)
        created = service.create_request(
            user_id="user-anon-1",
            idempotency_key="idem-anon-1",
            mode="anonymize",
            requested_by="user-anon-1",
        )

        fixed_now = datetime.fromisoformat("2026-02-28T12:00:00+00:00")
        processor = GovernanceDeletionProcessor(
            connection=connection,
            profile_service=profile_service,
            now_provider=lambda: fixed_now,
        )

        result = processor.run_once()
        assert result.claimed_count == 1
        assert result.completed_count == 1
        assert result.breached_sla_count == 0

        request_row = connection.execute(
            """
            SELECT status, due_at, completed_at
            FROM governance_deletion_requests
            WHERE id = ?
            """,
            (created.id,),
        ).fetchone()
        assert request_row is not None
        expected_due_at = (fixed_now + timedelta(days=DELETION_SLA_DAYS)).isoformat()
        assert request_row == ("completed", expected_due_at, fixed_now.isoformat())

        outbox_row = connection.execute(
            """
            SELECT user_id, subscription_id
            FROM notification_outbox
            WHERE id = ?
            """,
            ("outbox-anon-1",),
        ).fetchone()
        assert outbox_row is not None
        assert str(outbox_row[0]).startswith("anon-")
        assert str(outbox_row[0]) != "user-anon-1"
        assert outbox_row[1] is None
    finally:
        connection.close()



def test_reprocessing_completed_deletion_request_is_idempotent() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection)

        repository = InMemoryUserProfileRepository()
        profile_service = UserProfileService(
            repository=repository,
            supported_city_ids=(PILOT_CITY_ID,),
        )

        service = GovernanceDeletionService(connection=connection)
        created = service.create_request(
            user_id="user-idempotent-1",
            idempotency_key="idem-idempotent-1",
            mode="delete",
            requested_by="user-idempotent-1",
        )

        processor = GovernanceDeletionProcessor(
            connection=connection,
            profile_service=profile_service,
        )

        first = processor.run_once()
        assert first.claimed_count == 1
        assert first.completed_count == 1

        second = processor.run_once()
        assert second.claimed_count == 0
        assert second.completed_count == 0

        statuses = connection.execute(
            """
            SELECT to_status
            FROM governance_deletion_request_status_history
            WHERE request_id = ?
            ORDER BY id ASC
            """,
            (created.id,),
        ).fetchall()
        assert statuses == [
            ("requested",),
            ("accepted",),
            ("processing",),
            ("completed",),
        ]
    finally:
        connection.close()
