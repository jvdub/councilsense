from __future__ import annotations

from datetime import UTC, datetime

import pytest

from councilsense.api.profile import (
    InMemoryUserProfileRepository,
    SelfOnlyAuthorizationError,
    UserProfile,
    UserProfileService,
    is_pause_window_active,
)


def _service() -> UserProfileService:
    return UserProfileService(
        repository=InMemoryUserProfileRepository(),
        supported_city_ids=("seattle-wa", "portland-or"),
    )


def test_get_profile_for_subject_blocks_cross_user_access():
    service = _service()

    with pytest.raises(SelfOnlyAuthorizationError):
        service.get_profile_for_subject(actor_user_id="user-a", subject_user_id="user-b")


def test_patch_profile_for_subject_blocks_cross_user_access():
    service = _service()

    with pytest.raises(SelfOnlyAuthorizationError):
        service.patch_profile_for_subject(
            actor_user_id="user-a",
            subject_user_id="user-b",
            notifications_enabled=False,
        )


def test_pause_window_boundary_is_active_only_when_paused_until_is_in_future():
    as_of = datetime(2026, 2, 27, 12, 0, tzinfo=UTC)

    assert is_pause_window_active(as_of, as_of=as_of) is False
    assert is_pause_window_active(datetime(2026, 2, 27, 12, 1, tzinfo=UTC), as_of=as_of) is True
    assert is_pause_window_active(datetime(2026, 2, 27, 11, 59, tzinfo=UTC), as_of=as_of) is False


def test_pause_window_evaluation_is_timezone_safe_for_naive_values():
    as_of_aware = datetime(2026, 2, 27, 12, 0, tzinfo=UTC)
    paused_until_naive = datetime(2026, 2, 27, 12, 1)

    assert is_pause_window_active(paused_until_naive, as_of=as_of_aware) is True


def test_notification_eligibility_inactive_when_notifications_disabled():
    profile = UserProfile(
        user_id="user-a",
        notifications_enabled=False,
        notifications_paused_until=None,
    )

    eligibility = profile.notification_eligibility(as_of=datetime(2026, 2, 27, 12, 0, tzinfo=UTC))

    assert eligibility.notifications_enabled is False
    assert eligibility.pause_window_active is False
    assert eligibility.notifications_eligible is False


def test_notification_eligibility_inactive_when_pause_window_is_active():
    profile = UserProfile(
        user_id="user-a",
        notifications_enabled=True,
        notifications_paused_until=datetime(2026, 2, 27, 12, 30, tzinfo=UTC),
    )

    eligibility = profile.notification_eligibility(as_of=datetime(2026, 2, 27, 12, 0, tzinfo=UTC))

    assert eligibility.notifications_enabled is True
    assert eligibility.pause_window_active is True
    assert eligibility.notifications_eligible is False
