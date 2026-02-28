from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


NotificationOutboxStatus = Literal[
    "queued",
    "sending",
    "sent",
    "failed",
    "dlq",
    "suppressed",
    "invalid_subscription",
    "expired_subscription",
]

NotificationAttemptOutcome = Literal[
    "success",
    "retryable_failure",
    "permanent_failure",
    "suppressed",
    "invalid_subscription",
    "expired_subscription",
]


@dataclass(frozen=True)
class NotificationOutboxRecord:
    id: str
    user_id: str
    meeting_id: str
    city_id: str
    notification_type: str
    dedupe_key: str
    payload_json: str
    status: NotificationOutboxStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: str
    last_attempt_at: str | None
    error_code: str | None
    provider_response_summary: str | None
    subscription_id: str | None
    sent_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class NotificationDeliveryAttemptRecord:
    id: int
    outbox_id: str
    attempt_number: int
    outcome: NotificationAttemptOutcome
    error_code: str | None
    provider_response_summary: str | None
    next_retry_at: str | None
    attempted_at: str
    created_at: str


NotificationDlqFailureClassification = Literal[
    "transient",
    "permanent",
    "unknown",
]


@dataclass(frozen=True)
class NotificationDeliveryDlqRecord:
    id: int
    outbox_id: str
    notification_id: str
    message_id: str
    city_id: str
    source_id: str | None
    run_id: str | None
    meeting_id: str
    user_id: str
    notification_type: str
    failure_classification: NotificationDlqFailureClassification
    failure_reason_code: str | None
    failure_reason_summary: str | None
    terminal_attempt_number: int
    terminal_attempted_at: str
    terminal_transitioned_at: str
    replayed_at: str | None
    replayed_by: str | None
    replay_idempotency_key: str | None
    replay_outbox_id: str | None
    created_at: str
    updated_at: str
