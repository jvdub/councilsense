from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Literal, Sequence

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


NotificationMetricEmitter = Callable[[str, str, str, float], None]

_NOTIFY_ENQUEUE_STAGE = "notify_enqueue"
_NOTIFY_ENQUEUE_COUNTER = "councilsense_notifications_enqueue_events_total"
_UNKNOWN_RUN_ID = "run-unknown"


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
    run_id: str | None = None,
    metric_emitter: NotificationMetricEmitter | None = None,
) -> NotificationEnqueueResult:
    timestamp = enqueued_at or datetime.now(UTC)
    eligible_targets = select_eligible_subscription_targets(
        city_id=city_id,
        targets=subscription_targets,
    )

    enqueued_count = 0
    dedupe_conflict_count = 0
    normalized_run_id = _normalized_run_id(run_id)
    current_dedupe_key = "notification-outbox-batch"

    try:
        for target in eligible_targets:
            dedupe_key = build_notification_dedupe_key(
                user_id=target.user_id,
                meeting_id=meeting_id,
                notification_type=notification_type,
            )
            current_dedupe_key = dedupe_key
            payload = produce_notification_event_payload(
                user_id=target.user_id,
                meeting_id=meeting_id,
                notification_type=notification_type,
                enqueued_at=timestamp,
                subscription_id=target.subscription_id,
            )
            payload["run_id"] = normalized_run_id

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
                _emit_metric(
                    metric_emitter=metric_emitter,
                    name=_NOTIFY_ENQUEUE_COUNTER,
                    stage=_NOTIFY_ENQUEUE_STAGE,
                    outcome="success",
                )
                logger.info(
                    "notification_enqueue_attempt",
                    extra={
                        "event": {
                            "event_name": "notification_enqueue_attempt",
                            "city_id": city_id,
                            "meeting_id": meeting_id,
                            "run_id": normalized_run_id,
                            "dedupe_key": dedupe_key,
                            "stage": _NOTIFY_ENQUEUE_STAGE,
                            "outcome": "success",
                            "notification_type": notification_type,
                        }
                    },
                )
            else:
                dedupe_conflict_count += 1
                _emit_metric(
                    metric_emitter=metric_emitter,
                    name=_NOTIFY_ENQUEUE_COUNTER,
                    stage=_NOTIFY_ENQUEUE_STAGE,
                    outcome="duplicate",
                )
                logger.info(
                    "notification_enqueue_attempt",
                    extra={
                        "event": {
                            "event_name": "notification_enqueue_attempt",
                            "city_id": city_id,
                            "meeting_id": meeting_id,
                            "run_id": normalized_run_id,
                            "dedupe_key": dedupe_key,
                            "stage": _NOTIFY_ENQUEUE_STAGE,
                            "outcome": "duplicate",
                            "notification_type": notification_type,
                        }
                    },
                )
    except sqlite3.Error as exc:
        _emit_metric(
            metric_emitter=metric_emitter,
            name=_NOTIFY_ENQUEUE_COUNTER,
            stage=_NOTIFY_ENQUEUE_STAGE,
            outcome="failure",
        )
        logger.error(
            "notification_outbox_enqueue_failed",
            extra={
                "event": {
                    "event_name": "notification_outbox_enqueue_failed",
                    "city_id": city_id,
                    "meeting_id": meeting_id,
                    "run_id": normalized_run_id,
                    "dedupe_key": current_dedupe_key,
                    "stage": _NOTIFY_ENQUEUE_STAGE,
                    "outcome": "failure",
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
                "run_id": normalized_run_id,
                "dedupe_key": "notification-outbox-batch",
                "stage": _NOTIFY_ENQUEUE_STAGE,
                "outcome": "success" if result.enqueued_count > 0 else "duplicate",
                "notification_type": result.notification_type,
                "eligible_subscription_count": result.eligible_subscription_count,
                "enqueued_count": result.enqueued_count,
                "dedupe_conflict_count": result.dedupe_conflict_count,
            }
        },
    )
    return result


def _emit_metric(
    *,
    metric_emitter: NotificationMetricEmitter | None,
    name: str,
    stage: str,
    outcome: str,
    value: float = 1.0,
) -> None:
    if metric_emitter is None:
        return
    metric_emitter(name, stage, outcome, value)


def _normalized_run_id(run_id: str | None) -> str:
    if run_id is None:
        return _UNKNOWN_RUN_ID
    normalized = run_id.strip()
    if not normalized:
        return _UNKNOWN_RUN_ID
    return normalized