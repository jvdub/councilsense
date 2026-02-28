from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import logging
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.app.notification_contracts import produce_notification_event_payload
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


def _client(
    monkeypatch,
    *,
    secret: str,
    operator_user_ids: str,
    allow_permanent_override: bool = False,
) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    monkeypatch.setenv("NOTIFICATION_REPLAY_OPERATOR_USER_IDS", operator_user_ids)
    monkeypatch.setenv(
        "NOTIFICATION_REPLAY_ALLOW_PERMANENT_INVALID_OVERRIDE",
        "true" if allow_permanent_override else "false",
    )
    return TestClient(create_app())


def _insert_dlq_notification(
    client: TestClient,
    *,
    outbox_id: str,
    meeting_id: str,
    user_id: str,
    failure_classification: str,
) -> None:
    app = cast(Any, client.app)
    connection = app.state.db_connection

    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            meeting_id,
            PILOT_CITY_ID,
            f"uid-{meeting_id}",
            "Replay Test Meeting",
            "2026-02-28 12:00:00",
            "2026-02-28 12:00:00",
        ),
    )

    payload = produce_notification_event_payload(
        user_id=user_id,
        meeting_id=meeting_id,
        notification_type="meeting_published",
        enqueued_at=datetime(2026, 2, 28, 12, 0, tzinfo=UTC),
        subscription_id="sub-replay",
    )
    payload["delivery_status"] = "dlq"
    payload["attempt_count"] = 3
    payload["error_code"] = "provider_timeout"

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
            last_attempt_at,
            error_code,
            provider_response_summary,
            subscription_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'dlq', 3, 5, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            outbox_id,
            user_id,
            meeting_id,
            PILOT_CITY_ID,
            "meeting_published",
            str(payload["dedupe_key"]),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "2026-02-28T12:00:00+00:00",
            "2026-02-28T12:10:00+00:00",
            "provider_timeout",
            "provider timed out",
            "sub-replay",
        ),
    )

    connection.execute(
        """
        INSERT INTO notification_delivery_dlq (
            outbox_id,
            notification_id,
            message_id,
            city_id,
            source_id,
            run_id,
            meeting_id,
            user_id,
            notification_type,
            failure_classification,
            failure_reason_code,
            failure_reason_summary,
            terminal_attempt_number,
            terminal_attempted_at,
            terminal_transitioned_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            outbox_id,
            outbox_id,
            str(payload["dedupe_key"]),
            PILOT_CITY_ID,
            "source-seattle-minutes",
            "run-replay-test",
            meeting_id,
            user_id,
            "meeting_published",
            failure_classification,
            "provider_timeout",
            "provider timed out",
            3,
            "2026-02-28T12:10:00+00:00",
            "2026-02-28T12:10:00+00:00",
        ),
    )


def test_authorized_operator_can_replay_eligible_dlq_and_audit_linkage(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1")
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-eligible",
        meeting_id="meeting-replay-eligible",
        user_id="user-replay-eligible",
        failure_classification="transient",
    )

    token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)
    response = client.post(
        "/v1/operators/notifications/dlq/outbox-replay-eligible/replay",
        headers={"Authorization": f"Bearer {token}"},
        json={"idempotency_key": "replay-key-1", "reason": "provider recovered"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "requeued"
    assert body["source_outbox_id"] == "outbox-replay-eligible"
    assert body["replay_outbox_id"] == "outbox-replay-eligible"
    assert body["actor_user_id"] == "operator-1"
    assert body["replay_reason"] == "provider recovered"
    assert body["requeue_correlation_id"].startswith("requeue-correlation-")

    app = cast(Any, client.app)
    connection = app.state.db_connection

    outbox_row = connection.execute(
        """
        SELECT status, attempt_count, error_code, provider_response_summary
        FROM notification_outbox
        WHERE id = ?
        """,
        ("outbox-replay-eligible",),
    ).fetchone()
    assert outbox_row == ("queued", 0, None, None)

    audit_row = connection.execute(
        """
        SELECT
            source_outbox_id,
            replay_outbox_id,
            replay_idempotency_key,
            actor_user_id,
            replay_reason,
            outcome
        FROM notification_dlq_replay_audit
        WHERE replay_idempotency_key = ?
        """,
        ("replay-key-1",),
    ).fetchone()
    assert audit_row == (
        "outbox-replay-eligible",
        "outbox-replay-eligible",
        "replay-key-1",
        "operator-1",
        "provider recovered",
        "requeued",
    )


def test_unauthorized_operator_replay_attempt_is_denied_and_logged(monkeypatch, caplog) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1")
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-unauthorized",
        meeting_id="meeting-replay-unauthorized",
        user_id="user-replay-unauthorized",
        failure_classification="transient",
    )

    token = _issue_token("regular-user", secret=secret, expires_in_seconds=300)
    caplog.set_level(logging.WARNING)

    response = client.post(
        "/v1/operators/notifications/dlq/outbox-replay-unauthorized/replay",
        headers={"Authorization": f"Bearer {token}"},
        json={"idempotency_key": "replay-key-unauthorized", "reason": "attempt"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Operator replay action is forbidden"
    assert "notification_dlq_replay_unauthorized" in caplog.text


def test_permanent_dlq_replay_requires_override_policy_and_request_flag(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1", allow_permanent_override=False)
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-permanent",
        meeting_id="meeting-replay-permanent",
        user_id="user-replay-permanent",
        failure_classification="permanent",
    )

    token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)
    blocked = client.post(
        "/v1/operators/notifications/dlq/outbox-replay-permanent/replay",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "replay-key-permanent",
            "reason": "operator reviewed",
            "override_permanent_invalid": True,
        },
    )

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "permanent_failure_requires_policy_override"

    override_client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1", allow_permanent_override=True)
    _insert_dlq_notification(
        override_client,
        outbox_id="outbox-replay-permanent-override",
        meeting_id="meeting-replay-permanent-override",
        user_id="user-replay-permanent-override",
        failure_classification="permanent",
    )

    allowed_token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)
    allowed = override_client.post(
        "/v1/operators/notifications/dlq/outbox-replay-permanent-override/replay",
        headers={"Authorization": f"Bearer {allowed_token}"},
        json={
            "idempotency_key": "replay-key-permanent-override",
            "reason": "manual payload fix deployed",
            "override_permanent_invalid": True,
        },
    )

    assert allowed.status_code == 201
    assert allowed.json()["outcome"] == "requeued"


def test_replay_idempotency_key_prevents_double_requeue(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1")
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-idempotent",
        meeting_id="meeting-replay-idempotent",
        user_id="user-replay-idempotent",
        failure_classification="transient",
    )

    token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)
    first = client.post(
        "/v1/operators/notifications/dlq/outbox-replay-idempotent/replay",
        headers={"Authorization": f"Bearer {token}"},
        json={"idempotency_key": "replay-key-idempotent", "reason": "first replay"},
    )
    second = client.post(
        "/v1/operators/notifications/dlq/outbox-replay-idempotent/replay",
        headers={"Authorization": f"Bearer {token}"},
        json={"idempotency_key": "replay-key-idempotent", "reason": "second replay"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["requeue_correlation_id"] == second.json()["requeue_correlation_id"]

    app = cast(Any, client.app)
    connection = app.state.db_connection
    audit_count = connection.execute(
        "SELECT COUNT(*) FROM notification_dlq_replay_audit WHERE replay_idempotency_key = ?",
        ("replay-key-idempotent",),
    ).fetchone()
    assert audit_count is not None
    assert int(audit_count[0]) == 1
