from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import logging
import threading
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.app.notification_contracts import produce_notification_event_payload
from councilsense.app.notification_dlq_replay import NotificationDlqReplayService
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


def test_replay_concurrent_attempts_on_same_dlq_item_prevent_duplicate_requeue(monkeypatch) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1")
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-concurrency",
        meeting_id="meeting-replay-concurrency",
        user_id="user-replay-concurrency",
        failure_classification="transient",
    )

    app = cast(Any, client.app)
    metrics: list[tuple[str, str, str, float]] = []

    def _metric_emitter(name: str, stage: str, outcome: str, value: float) -> None:
        metrics.append((name, stage, outcome, value))

    app.state.notification_dlq_replay_service = NotificationDlqReplayService(
        connection=app.state.db_connection,
        allow_permanent_invalid_override=False,
        metric_emitter=_metric_emitter,
    )

    token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)
    start_barrier = threading.Barrier(3)

    def _invoke(idempotency_key: str) -> tuple[int, dict[str, Any]]:
        start_barrier.wait(timeout=2)
        response = client.post(
            "/v1/operators/notifications/dlq/outbox-replay-concurrency/replay",
            headers={"Authorization": f"Bearer {token}"},
            json={"idempotency_key": idempotency_key, "reason": "concurrency replay gate"},
        )
        return response.status_code, cast(dict[str, Any], response.json())

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_invoke, "replay-key-concurrency-1")
        second = executor.submit(_invoke, "replay-key-concurrency-2")
        start_barrier.wait(timeout=2)
        first_status, first_body = first.result(timeout=5)
        second_status, second_body = second.result(timeout=5)

    assert first_status in {200, 201}
    assert second_status in {200, 201}
    outcomes = sorted((str(first_body["outcome"]), str(second_body["outcome"])))
    assert outcomes == ["duplicate", "requeued"]

    connection = app.state.db_connection
    replayed_dlq_count_row = connection.execute(
        "SELECT COUNT(*) FROM notification_delivery_dlq WHERE replay_outbox_id IS NOT NULL",
    ).fetchone()
    assert replayed_dlq_count_row is not None
    assert int(replayed_dlq_count_row[0]) == 1

    requeued_count_row = connection.execute(
        "SELECT COUNT(*) FROM notification_dlq_replay_audit WHERE source_outbox_id = ? AND outcome = 'requeued'",
        ("outbox-replay-concurrency",),
    ).fetchone()
    assert requeued_count_row is not None
    assert int(requeued_count_row[0]) == 1

    assert (
        "councilsense_notifications_dlq_replay_duplicate_prevention_hits_total",
        "notify_dlq_replay",
        "duplicate",
        1.0,
    ) in metrics


def test_replay_idempotency_gate_report_has_zero_duplicate_emission(monkeypatch, caplog) -> None:
    secret = "test-secret"
    client = _client(monkeypatch, secret=secret, operator_user_ids="operator-1", allow_permanent_override=False)
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-report-transient",
        meeting_id="meeting-replay-report-transient",
        user_id="user-replay-report-transient",
        failure_classification="transient",
    )
    _insert_dlq_notification(
        client,
        outbox_id="outbox-replay-report-permanent",
        meeting_id="meeting-replay-report-permanent",
        user_id="user-replay-report-permanent",
        failure_classification="permanent",
    )

    app = cast(Any, client.app)
    metrics: list[tuple[str, str, str, float]] = []

    def _metric_emitter(name: str, stage: str, outcome: str, value: float) -> None:
        metrics.append((name, stage, outcome, value))

    app.state.notification_dlq_replay_service = NotificationDlqReplayService(
        connection=app.state.db_connection,
        allow_permanent_invalid_override=False,
        metric_emitter=_metric_emitter,
    )

    token = _issue_token("operator-1", secret=secret, expires_in_seconds=300)

    with caplog.at_level(logging.INFO):
        replay_success = client.post(
            "/v1/operators/notifications/dlq/outbox-replay-report-transient/replay",
            headers={"Authorization": f"Bearer {token}"},
            json={"idempotency_key": "replay-key-report-1", "reason": "success path"},
        )
        replay_duplicate = client.post(
            "/v1/operators/notifications/dlq/outbox-replay-report-transient/replay",
            headers={"Authorization": f"Bearer {token}"},
            json={"idempotency_key": "replay-key-report-2", "reason": "duplicate path"},
        )
        replay_ineligible = client.post(
            "/v1/operators/notifications/dlq/outbox-replay-report-permanent/replay",
            headers={"Authorization": f"Bearer {token}"},
            json={"idempotency_key": "replay-key-report-3", "reason": "failure path"},
        )

    assert replay_success.status_code == 201
    assert replay_success.json()["outcome"] == "requeued"
    assert replay_duplicate.status_code == 200
    assert replay_duplicate.json()["outcome"] == "duplicate"
    assert replay_ineligible.status_code == 409
    assert replay_ineligible.json()["detail"] == "permanent_failure_requires_policy_override"

    connection = app.state.db_connection
    duplicate_emission_row = connection.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN replay_count > 1 THEN replay_count - 1 ELSE 0 END), 0)
        FROM (
            SELECT source_outbox_id, COUNT(*) AS replay_count
            FROM notification_dlq_replay_audit
            WHERE outcome = 'requeued'
            GROUP BY source_outbox_id
        )
        """,
    ).fetchone()
    assert duplicate_emission_row is not None

    replay_quality_report = {
        "replay_success_count": 1,
        "replay_duplicate_count": 1,
        "replay_failure_count": 1,
        "duplicate_notification_emissions": int(duplicate_emission_row[0]),
    }

    assert replay_quality_report["duplicate_notification_emissions"] == 0
    assert replay_quality_report["replay_success_count"] == 1
    assert replay_quality_report["replay_duplicate_count"] == 1
    assert replay_quality_report["replay_failure_count"] == 1

    replay_attempt_events: list[dict[str, object]] = []
    for record in caplog.records:
        event = getattr(record, "event", None)
        if isinstance(event, dict) and event.get("event_name") == "notification_dlq_replay_attempt":
            replay_attempt_events.append(event)

    assert len(replay_attempt_events) == 3
    assert {
        str(event["outcome"])
        for event in replay_attempt_events
    } == {"requeued", "duplicate", "ineligible"}
    assert (
        "councilsense_notifications_dlq_replay_duplicate_prevention_hits_total",
        "notify_dlq_replay",
        "duplicate",
        1.0,
    ) in metrics
