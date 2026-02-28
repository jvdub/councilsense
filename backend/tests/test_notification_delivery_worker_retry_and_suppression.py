from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from councilsense.app.notification_contracts import produce_notification_event_payload
from councilsense.app.notification_delivery_worker import (
    ExpiredSubscriptionDeliveryError,
    InvalidSubscriptionDeliveryError,
    NotificationDeliveryWorker,
    NotificationDeliveryWorkerConfig,
    RetryableDeliveryError,
)
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


class _DeterministicNow:
    def __init__(self, values: list[datetime]) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> datetime:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str, city_id: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, f"uid-{meeting_id}", "Council Meeting"),
    )


def _insert_outbox_row(
    connection: sqlite3.Connection,
    *,
    outbox_id: str,
    user_id: str,
    meeting_id: str,
    city_id: str,
    subscription_id: str,
    max_attempts: int,
) -> None:
    payload = produce_notification_event_payload(
        user_id=user_id,
        meeting_id=meeting_id,
        notification_type="meeting_published",
        enqueued_at=datetime(2026, 2, 27, 12, 0, tzinfo=UTC),
        subscription_id=subscription_id,
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
            outbox_id,
            user_id,
            meeting_id,
            city_id,
            "meeting_published",
            str(payload["dedupe_key"]),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "queued",
            0,
            max_attempts,
            "2026-02-27T12:00:00+00:00",
            subscription_id,
        ),
    )


def _base_seed(connection: sqlite3.Connection, *, meeting_id: str) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id=meeting_id, city_id=PILOT_CITY_ID)


def test_delivery_worker_retries_transient_failures_until_terminal_failure() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _base_seed(connection, meeting_id="meeting-delivery-retry")
        _insert_outbox_row(
            connection,
            outbox_id="outbox-retry",
            user_id="user-retry",
            meeting_id="meeting-delivery-retry",
            city_id=PILOT_CITY_ID,
            subscription_id="sub-retry",
            max_attempts=3,
        )

        now = _DeterministicNow(
            [
                datetime(2026, 2, 27, 12, 0, tzinfo=UTC),
                datetime(2026, 2, 27, 12, 0, tzinfo=UTC),
                datetime(2026, 2, 27, 12, 1, tzinfo=UTC),
                datetime(2026, 2, 27, 12, 1, tzinfo=UTC),
                datetime(2026, 2, 27, 12, 2, tzinfo=UTC),
                datetime(2026, 2, 27, 12, 2, tzinfo=UTC),
            ]
        )
        attempts = {"count": 0}

        def _always_transient_fail(_: object) -> None:
            attempts["count"] += 1
            raise RetryableDeliveryError(
                error_code="provider_timeout",
                provider_response_summary="provider timed out",
            )

        worker = NotificationDeliveryWorker(
            connection=connection,
            sender=_always_transient_fail,
            config=NotificationDeliveryWorkerConfig(claim_batch_size=1, retry_backoff_seconds=(60, 60, 60)),
            now_provider=now,
        )

        first = worker.run_once()
        second = worker.run_once()
        third = worker.run_once()

        assert first.retried_count == 1
        assert second.retried_count == 1
        assert third.failed_count == 1
        assert attempts["count"] == 3

        outbox_row = connection.execute(
            """
            SELECT status, attempt_count, error_code, provider_response_summary
            FROM notification_outbox
            WHERE id = ?
            """,
            ("outbox-retry",),
        ).fetchone()
        assert outbox_row == ("failed", 3, "provider_timeout", "provider timed out")

        attempt_rows = connection.execute(
            """
            SELECT attempt_number, outcome, next_retry_at
            FROM notification_delivery_attempts
            WHERE outbox_id = ?
            ORDER BY attempt_number ASC
            """,
            ("outbox-retry",),
        ).fetchall()
        assert [row[0] for row in attempt_rows] == [1, 2, 3]
        assert [row[1] for row in attempt_rows] == ["retryable_failure", "retryable_failure", "permanent_failure"]
        assert attempt_rows[0][2] is not None
        assert attempt_rows[1][2] is not None
        assert attempt_rows[2][2] is None
    finally:
        connection.close()


def test_delivery_worker_marks_invalid_and_expired_subscriptions_as_suppressed() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _base_seed(connection, meeting_id="meeting-delivery-suppression")
        _insert_outbox_row(
            connection,
            outbox_id="outbox-invalid",
            user_id="user-invalid",
            meeting_id="meeting-delivery-suppression",
            city_id=PILOT_CITY_ID,
            subscription_id="sub-invalid",
            max_attempts=4,
        )
        _insert_outbox_row(
            connection,
            outbox_id="outbox-expired",
            user_id="user-expired",
            meeting_id="meeting-delivery-suppression",
            city_id=PILOT_CITY_ID,
            subscription_id="sub-expired",
            max_attempts=4,
        )

        suppressed: list[tuple[str, str]] = []

        def _suppression_sink(subscription_id: str, reason: str) -> None:
            suppressed.append((subscription_id, reason))

        def _provider_sender(row: object) -> None:
            outbox_id = getattr(row, "id")
            if outbox_id == "outbox-invalid":
                raise InvalidSubscriptionDeliveryError(
                    error_code="push_410",
                    provider_response_summary="endpoint gone",
                )
            if outbox_id == "outbox-expired":
                raise ExpiredSubscriptionDeliveryError(
                    error_code="push_expired",
                    provider_response_summary="subscription expired",
                )

        worker = NotificationDeliveryWorker(
            connection=connection,
            sender=_provider_sender,
            suppression_sink=_suppression_sink,
            config=NotificationDeliveryWorkerConfig(claim_batch_size=2),
            now_provider=lambda: datetime(2026, 2, 27, 12, 30, tzinfo=UTC),
        )

        result = worker.run_once()
        assert result.suppressed_count == 2

        status_rows = connection.execute(
            """
            SELECT id, status, attempt_count
            FROM notification_outbox
            WHERE id IN ('outbox-invalid', 'outbox-expired')
            ORDER BY id ASC
            """
        ).fetchall()
        assert status_rows == [
            ("outbox-expired", "expired_subscription", 1),
            ("outbox-invalid", "invalid_subscription", 1),
        ]

        attempt_rows = connection.execute(
            """
            SELECT outbox_id, attempt_number, outcome, next_retry_at
            FROM notification_delivery_attempts
            WHERE outbox_id IN ('outbox-invalid', 'outbox-expired')
            ORDER BY outbox_id ASC
            """
        ).fetchall()
        assert attempt_rows == [
            ("outbox-expired", 1, "expired_subscription", None),
            ("outbox-invalid", 1, "invalid_subscription", None),
        ]
        assert sorted(suppressed) == [
            ("sub-expired", "expired_subscription"),
            ("sub-invalid", "invalid_subscription"),
        ]
    finally:
        connection.close()


def test_delivery_worker_claiming_is_safe_with_two_concurrent_workers(tmp_path: Path) -> None:
    db_path = tmp_path / "delivery-worker-concurrency.db"

    setup_connection = sqlite3.connect(str(db_path))
    setup_connection.execute("PRAGMA foreign_keys = ON")
    try:
        _base_seed(setup_connection, meeting_id="meeting-delivery-concurrency")
        _insert_outbox_row(
            setup_connection,
            outbox_id="outbox-concurrency",
            user_id="user-concurrency",
            meeting_id="meeting-delivery-concurrency",
            city_id=PILOT_CITY_ID,
            subscription_id="sub-concurrency",
            max_attempts=3,
        )
        setup_connection.commit()
    finally:
        setup_connection.close()

    sender_calls = {"count": 0}
    sender_lock = threading.Lock()
    start_barrier = threading.Barrier(2)

    def _sender(_: object) -> None:
        with sender_lock:
            sender_calls["count"] += 1

    def _run_worker() -> None:
        connection = sqlite3.connect(str(db_path), timeout=5.0)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            worker = NotificationDeliveryWorker(
                connection=connection,
                sender=_sender,
                config=NotificationDeliveryWorkerConfig(claim_batch_size=1),
                now_provider=lambda: datetime(2026, 2, 27, 13, 0, tzinfo=UTC),
            )
            start_barrier.wait(timeout=5.0)
            worker.run_once()
        finally:
            connection.close()

    threads = [threading.Thread(target=_run_worker), threading.Thread(target=_run_worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    verify_connection = sqlite3.connect(str(db_path))
    verify_connection.execute("PRAGMA foreign_keys = ON")
    try:
        outbox = verify_connection.execute(
            "SELECT status, attempt_count FROM notification_outbox WHERE id = ?",
            ("outbox-concurrency",),
        ).fetchone()
        assert outbox == ("sent", 1)

        attempt_count = verify_connection.execute(
            "SELECT COUNT(*) FROM notification_delivery_attempts WHERE outbox_id = ?",
            ("outbox-concurrency",),
        ).fetchone()
        assert attempt_count is not None
        assert int(attempt_count[0]) == 1
        assert sender_calls["count"] == 1
    finally:
        verify_connection.close()