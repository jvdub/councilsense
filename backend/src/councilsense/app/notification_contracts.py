from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Mapping

NOTIFICATION_CONTRACT_VERSION = "st-009-v1"
NOTIFICATION_DEDUPE_KEY_PREFIX = "notif-dedupe-v1"


class NotificationContractError(ValueError):
    def __init__(self, *, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Invalid notification payload field '{field}': {reason}")


def _required_string(*, payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if value is None:
        raise NotificationContractError(field=field, reason="missing")
    if not isinstance(value, str):
        raise NotificationContractError(field=field, reason="must be a string")
    normalized = value.strip()
    if not normalized:
        raise NotificationContractError(field=field, reason="must be non-empty")
    return normalized


def _optional_string(*, payload: Mapping[str, object], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise NotificationContractError(field=field, reason="must be a string")
    normalized = value.strip()
    if not normalized:
        raise NotificationContractError(field=field, reason="must be non-empty when present")
    return normalized


def _required_datetime(*, payload: Mapping[str, object], field: str) -> datetime:
    value = payload.get(field)
    if value is None:
        raise NotificationContractError(field=field, reason="missing")
    if not isinstance(value, str):
        raise NotificationContractError(field=field, reason="must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise NotificationContractError(field=field, reason="must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise NotificationContractError(field=field, reason="must include timezone offset")
    return parsed


def _required_int(*, payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if value is None:
        raise NotificationContractError(field=field, reason="missing")
    if not isinstance(value, int):
        raise NotificationContractError(field=field, reason="must be an integer")
    return value


def build_notification_dedupe_key(*, user_id: str, meeting_id: str, notification_type: str) -> str:
    normalized_user_id = _required_string(payload={"user_id": user_id}, field="user_id")
    normalized_meeting_id = _required_string(payload={"meeting_id": meeting_id}, field="meeting_id")
    normalized_notification_type = _required_string(
        payload={"notification_type": notification_type},
        field="notification_type",
    ).lower()
    digest_input = "\x1f".join((normalized_user_id, normalized_meeting_id, normalized_notification_type))
    digest = sha256(digest_input.encode("utf-8")).hexdigest()
    return f"{NOTIFICATION_DEDUPE_KEY_PREFIX}:{digest}"


@dataclass(frozen=True)
class NotificationDeliveryStatusModel:
    transitions: Mapping[str, tuple[str, ...]]

    def can_transition(self, *, current: str, next_status: str) -> bool:
        allowed = self.transitions.get(current)
        if allowed is None:
            return False
        return next_status in allowed


NOTIFICATION_DELIVERY_STATUS_MODEL = NotificationDeliveryStatusModel(
    transitions={
        "queued": (
            "sending",
            "suppressed",
            "invalid_subscription",
            "expired_subscription",
        ),
        "sending": (
            "sent",
            "failed",
            "dlq",
            "suppressed",
            "invalid_subscription",
            "expired_subscription",
        ),
        "failed": (
            "sending",
            "suppressed",
            "invalid_subscription",
            "expired_subscription",
        ),
        "dlq": (),
        "sent": (),
        "suppressed": (),
        "invalid_subscription": (),
        "expired_subscription": (),
    }
)


@dataclass(frozen=True)
class NotificationEventMessage:
    contract_version: str
    user_id: str
    meeting_id: str
    notification_type: str
    dedupe_key: str
    enqueued_at: datetime
    delivery_status: str
    subscription_id: str | None = None
    attempt_count: int = 0
    error_code: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> NotificationEventMessage:
        contract_version = _required_string(payload=payload, field="contract_version")
        if contract_version != NOTIFICATION_CONTRACT_VERSION:
            raise NotificationContractError(
                field="contract_version",
                reason=f"must be '{NOTIFICATION_CONTRACT_VERSION}'",
            )

        user_id = _required_string(payload=payload, field="user_id")
        meeting_id = _required_string(payload=payload, field="meeting_id")
        notification_type = _required_string(payload=payload, field="notification_type")
        dedupe_key = _required_string(payload=payload, field="dedupe_key")
        expected_dedupe_key = build_notification_dedupe_key(
            user_id=user_id,
            meeting_id=meeting_id,
            notification_type=notification_type,
        )
        if dedupe_key != expected_dedupe_key:
            raise NotificationContractError(
                field="dedupe_key",
                reason="must match deterministic key derived from user_id, meeting_id, notification_type",
            )

        delivery_status = _required_string(payload=payload, field="delivery_status")
        if delivery_status not in NOTIFICATION_DELIVERY_STATUS_MODEL.transitions:
            raise NotificationContractError(field="delivery_status", reason="unknown status")

        attempt_count = _required_int(payload=payload, field="attempt_count")
        if attempt_count < 0:
            raise NotificationContractError(field="attempt_count", reason="must be >= 0")

        return cls(
            contract_version=contract_version,
            user_id=user_id,
            meeting_id=meeting_id,
            notification_type=notification_type,
            dedupe_key=dedupe_key,
            enqueued_at=_required_datetime(payload=payload, field="enqueued_at"),
            delivery_status=delivery_status,
            subscription_id=_optional_string(payload=payload, field="subscription_id"),
            attempt_count=attempt_count,
            error_code=_optional_string(payload=payload, field="error_code"),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "user_id": self.user_id,
            "meeting_id": self.meeting_id,
            "notification_type": self.notification_type,
            "dedupe_key": self.dedupe_key,
            "enqueued_at": self.enqueued_at.astimezone(UTC).isoformat(),
            "delivery_status": self.delivery_status,
            "subscription_id": self.subscription_id,
            "attempt_count": self.attempt_count,
            "error_code": self.error_code,
        }


def produce_notification_event_payload(
    *,
    user_id: str,
    meeting_id: str,
    notification_type: str,
    enqueued_at: datetime,
    subscription_id: str | None = None,
) -> dict[str, object]:
    message = NotificationEventMessage(
        contract_version=NOTIFICATION_CONTRACT_VERSION,
        user_id=user_id,
        meeting_id=meeting_id,
        notification_type=notification_type,
        dedupe_key=build_notification_dedupe_key(
            user_id=user_id,
            meeting_id=meeting_id,
            notification_type=notification_type,
        ),
        enqueued_at=enqueued_at,
        delivery_status="queued",
        subscription_id=subscription_id,
        attempt_count=0,
        error_code=None,
    )
    return NotificationEventMessage.from_payload(message.to_payload()).to_payload()


def consume_notification_event_payload(payload: Mapping[str, object]) -> NotificationEventMessage:
    return NotificationEventMessage.from_payload(payload)
