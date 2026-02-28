from __future__ import annotations

from datetime import UTC, datetime

import pytest

from councilsense.app.notification_contracts import (
    NOTIFICATION_CONTRACT_VERSION,
    NOTIFICATION_DELIVERY_STATUS_MODEL,
    NotificationContractError,
    build_notification_dedupe_key,
    consume_notification_event_payload,
    produce_notification_event_payload,
)


def test_notification_dedupe_key_is_deterministic_and_varies_by_tuple() -> None:
    stable_one = build_notification_dedupe_key(
        user_id="user-123",
        meeting_id="meeting-abc",
        notification_type="meeting_published",
    )
    stable_two = build_notification_dedupe_key(
        user_id="user-123",
        meeting_id="meeting-abc",
        notification_type="meeting_published",
    )
    different_type = build_notification_dedupe_key(
        user_id="user-123",
        meeting_id="meeting-abc",
        notification_type="agenda_changed",
    )

    assert stable_one == stable_two
    assert stable_one != different_type


def test_notification_contract_accepts_valid_payload_and_rejects_invalid_payload() -> None:
    valid_payload = produce_notification_event_payload(
        user_id="user-123",
        meeting_id="meeting-abc",
        notification_type="meeting_published",
        enqueued_at=datetime(2026, 2, 27, 17, 45, tzinfo=UTC),
        subscription_id="sub-999",
    )

    parsed = consume_notification_event_payload(valid_payload)

    assert parsed.contract_version == NOTIFICATION_CONTRACT_VERSION
    assert parsed.delivery_status == "queued"
    assert parsed.attempt_count == 0

    invalid_payload = dict(valid_payload)
    invalid_payload["meeting_id"] = ""

    with pytest.raises(NotificationContractError) as exc:
        consume_notification_event_payload(invalid_payload)

    assert exc.value.field == "meeting_id"


def test_notification_delivery_status_transitions_are_unambiguous() -> None:
    assert NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="queued", next_status="sending")
    assert NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status="sent")
    assert NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sending", next_status="dlq")
    assert NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="failed", next_status="sending")
    assert not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="sent", next_status="sending")
    assert not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="dlq", next_status="sending")
    assert not NOTIFICATION_DELIVERY_STATUS_MODEL.can_transition(current="invalid_subscription", next_status="sending")
