from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime

import pytest

from councilsense.app.notification_contracts import produce_notification_event_payload
from councilsense.app.notification_delivery_worker import (
    NotificationDeliveryWorker,
    NotificationDeliveryWorkerConfig,
    RetryableDeliveryError,
)
from councilsense.app.notification_fanout import (
    NotificationSubscriptionTarget,
    enqueue_publish_notifications_to_outbox,
)
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str, city_id: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, f"uid-{meeting_id}", "Council Meeting"),
    )


class _DeterministicNow:
    def __init__(self, values: list[datetime]) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> datetime:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


def test_notification_enqueue_emits_contract_logs_and_metrics(caplog: pytest.LogCaptureFixture) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection)
        seed_city_registry(connection)
        _create_meeting(connection, meeting_id="meeting-notify-enqueue-obsv", city_id=PILOT_CITY_ID)

        metrics: list[tuple[str, str, str, float]] = []

        def _metric_emitter(name: str, stage: str, outcome: str, value: float) -> None:
            metrics.append((name, stage, outcome, value))

        targets = (
            NotificationSubscriptionTarget(
                user_id="user-enqueue-obsv",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-enqueue-obsv",
                status="active",
            ),
        )

        with caplog.at_level(logging.INFO):
            enqueue_publish_notifications_to_outbox(
                connection=connection,
                city_id=PILOT_CITY_ID,
                meeting_id="meeting-notify-enqueue-obsv",
                subscription_targets=targets,
                run_id="run-20260228-01",
                metric_emitter=_metric_emitter,
            )
            enqueue_publish_notifications_to_outbox(
                connection=connection,
                city_id=PILOT_CITY_ID,
                meeting_id="meeting-notify-enqueue-obsv",
                subscription_targets=targets,
                run_id="run-20260228-01",
                metric_emitter=_metric_emitter,
            )

        assert metrics == [
            ("councilsense_notifications_enqueue_events_total", "notify_enqueue", "success", 1.0),
            ("councilsense_notifications_enqueue_events_total", "notify_enqueue", "duplicate", 1.0),
        ]

        enqueue_events: list[dict[str, object]] = []
        for record in caplog.records:
            event = getattr(record, "event", None)
            if isinstance(event, dict) and event.get("event_name") == "notification_enqueue_attempt":
                enqueue_events.append(event)
        assert len(enqueue_events) == 2

        required_keys = {"city_id", "meeting_id", "run_id", "dedupe_key", "stage", "outcome"}
        for event in enqueue_events:
            assert required_keys.issubset(set(event.keys()))
            assert event["stage"] == "notify_enqueue"
        assert {event["outcome"] for event in enqueue_events} == {"success", "duplicate"}
    finally:
        connection.close()


def test_notification_delivery_emits_retry_terminal_latency_and_contract_logs(caplog: pytest.LogCaptureFixture) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        apply_migrations(connection)
        seed_city_registry(connection)
        _create_meeting(connection, meeting_id="meeting-notify-delivery-obsv", city_id=PILOT_CITY_ID)

        payload = produce_notification_event_payload(
            user_id="user-delivery-obsv",
            meeting_id="meeting-notify-delivery-obsv",
            notification_type="meeting_published",
            enqueued_at=datetime(2026, 2, 28, 12, 0, tzinfo=UTC),
            subscription_id="sub-delivery-obsv",
        )
        payload["run_id"] = "run-20260228-02"

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
                "outbox-notify-delivery-obsv",
                "user-delivery-obsv",
                "meeting-notify-delivery-obsv",
                PILOT_CITY_ID,
                "meeting_published",
                str(payload["dedupe_key"]),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                "queued",
                0,
                2,
                "2026-02-28T12:00:00+00:00",
                "sub-delivery-obsv",
            ),
        )

        metrics: list[tuple[str, str, str, float]] = []

        def _metric_emitter(name: str, stage: str, outcome: str, value: float) -> None:
            metrics.append((name, stage, outcome, value))

        sender_calls = {"count": 0}

        def _sender(_: object) -> None:
            sender_calls["count"] += 1
            raise RetryableDeliveryError(
                error_code="provider_timeout",
                provider_response_summary="provider timed out  due to transient overload",
            )

        worker = NotificationDeliveryWorker(
            connection=connection,
            sender=_sender,
            metric_emitter=_metric_emitter,
            config=NotificationDeliveryWorkerConfig(
                claim_batch_size=1,
                retry_backoff_seconds=(60, 60),
                retry_policy_version="policy-obsv-v1",
            ),
            now_provider=_DeterministicNow(
                [
                    datetime(2026, 2, 28, 12, 5, tzinfo=UTC),
                    datetime(2026, 2, 28, 12, 5, tzinfo=UTC),
                    datetime(2026, 2, 28, 12, 6, tzinfo=UTC),
                    datetime(2026, 2, 28, 12, 6, tzinfo=UTC),
                ]
            ),
        )

        with caplog.at_level(logging.INFO):
            first = worker.run_once()
            second = worker.run_once()

        assert first.retried_count == 1
        assert second.failed_count == 1
        assert sender_calls["count"] == 2

        counter_metrics = [
            item
            for item in metrics
            if item[0] == "councilsense_notifications_delivery_events_total"
        ]
        assert counter_metrics == [
            ("councilsense_notifications_delivery_events_total", "notify_deliver", "retry", 1.0),
            ("councilsense_notifications_delivery_events_total", "notify_deliver", "failure", 1.0),
        ]

        duration_metrics = [
            item
            for item in metrics
            if item[0] == "councilsense_notifications_delivery_duration_seconds"
        ]
        assert duration_metrics == [
            ("councilsense_notifications_delivery_duration_seconds", "notify_deliver", "retry", 300.0),
            ("councilsense_notifications_delivery_duration_seconds", "notify_deliver", "failure", 360.0),
        ]

        delivery_events: list[dict[str, object]] = []
        for record in caplog.records:
            event = getattr(record, "event", None)
            if isinstance(event, dict) and event.get("event_name") == "notification_delivery_attempt":
                delivery_events.append(event)
        assert len(delivery_events) == 2

        required_keys = {"city_id", "meeting_id", "run_id", "dedupe_key", "stage", "outcome"}
        for event in delivery_events:
            assert required_keys.issubset(set(event.keys()))
            assert event["stage"] == "notify_deliver"
            assert event["run_id"] == "run-20260228-02"
            assert event["retry_policy_version"] == "policy-obsv-v1"
            assert event["error_code"] == "provider_timeout"
            assert event["error_summary"] == "provider timed out due to transient overload"

        assert {event["outcome"] for event in delivery_events} == {"retry", "failure"}
    finally:
        connection.close()
