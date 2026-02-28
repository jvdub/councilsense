from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Sequence

from councilsense.app.notification_contracts import (
    build_notification_dedupe_key,
    produce_notification_event_payload,
)


NotificationSubscriptionStatus = Literal[
    "active",
    "invalid",
    "expired",
    "suppressed",
]


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationSubscriptionTarget:
    user_id: str
    city_id: str
    subscription_id: str
    status: NotificationSubscriptionStatus


@dataclass(frozen=True)
class NotificationEnqueueResult:
    city_id: str
    meeting_id: str
    notification_type: str
    eligible_subscription_count: int
    enqueued_count: int
    dedupe_conflict_count: int


def select_eligible_subscription_targets(
    *,
    city_id: str,
    targets: Sequence[NotificationSubscriptionTarget],
) -> tuple[NotificationSubscriptionTarget, ...]:
    normalized_city_id = city_id.strip()
    eligible: list[NotificationSubscriptionTarget] = []

    for target in targets:
        if target.city_id.strip() != normalized_city_id:
            continue
        if target.status != "active":
            continue
        if not target.user_id.strip() or not target.subscription_id.strip():
            continue
        eligible.append(target)

    return tuple(eligible)


def enqueue_publish_notifications_to_outbox(
    *,
    connection: sqlite3.Connection,
    city_id: str,
    meeting_id: str,
    subscription_targets: Sequence[NotificationSubscriptionTarget],
    notification_type: str = "meeting_published",
    enqueued_at: datetime | None = None,
) -> NotificationEnqueueResult:
    timestamp = enqueued_at or datetime.now(UTC)
    eligible_targets = select_eligible_subscription_targets(
        city_id=city_id,
        targets=subscription_targets,
    )

    enqueued_count = 0
    dedupe_conflict_count = 0

    try:
        for target in eligible_targets:
            dedupe_key = build_notification_dedupe_key(
                user_id=target.user_id,
                meeting_id=meeting_id,
                notification_type=notification_type,
            )
            payload = produce_notification_event_payload(
                user_id=target.user_id,
                meeting_id=meeting_id,
                notification_type=notification_type,
                enqueued_at=timestamp,
                subscription_id=target.subscription_id,
            )

            cursor = connection.execute(
                """
                INSERT INTO notification_outbox (
                    id,
                    user_id,
                    meeting_id,
                    city_id,
                    notification_type,
                    dedupe_key,
                    payload_json,
                    subscription_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dedupe_key) DO NOTHING
                """,
                (
                    f"outbox:{dedupe_key}",
                    target.user_id,
                    meeting_id,
                    city_id,
                    notification_type,
                    dedupe_key,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    target.subscription_id,
                ),
            )
            if cursor.rowcount > 0:
                enqueued_count += 1
            else:
                dedupe_conflict_count += 1
    except sqlite3.Error as exc:
        logger.error(
            "notification_outbox_enqueue_failed",
            extra={
                "event": {
                    "event_name": "notification_outbox_enqueue_failed",
                    "city_id": city_id,
                    "meeting_id": meeting_id,
                    "notification_type": notification_type,
                    "eligible_subscription_count": len(eligible_targets),
                    "error": str(exc),
                }
            },
        )
        raise

    result = NotificationEnqueueResult(
        city_id=city_id,
        meeting_id=meeting_id,
        notification_type=notification_type,
        eligible_subscription_count=len(eligible_targets),
        enqueued_count=enqueued_count,
        dedupe_conflict_count=dedupe_conflict_count,
    )
    logger.info(
        "notification_outbox_enqueue_result",
        extra={
            "event": {
                "event_name": "notification_outbox_enqueue_result",
                "city_id": result.city_id,
                "meeting_id": result.meeting_id,
                "notification_type": result.notification_type,
                "eligible_subscription_count": result.eligible_subscription_count,
                "enqueued_count": result.enqueued_count,
                "dedupe_conflict_count": result.dedupe_conflict_count,
            }
        },
    )
    return result