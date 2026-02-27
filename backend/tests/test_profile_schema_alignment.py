from __future__ import annotations

from datetime import UTC, datetime

from councilsense.api.profile import InMemoryUserProfileRepository, UserProfile


class _LegacyProfile:
    def __init__(self, *, user_id: str, home_city_id: str | None) -> None:
        self.user_id = user_id
        self.home_city_id = home_city_id


def test_profile_schema_defaults_are_present_for_new_profiles():
    repository = InMemoryUserProfileRepository()

    profile = repository.get_or_create("user-new")

    assert profile == UserProfile(
        user_id="user-new",
        home_city_id=None,
        notifications_enabled=True,
        notifications_paused_until=None,
    )


def test_existing_legacy_profile_records_are_backfilled_with_new_preference_fields():
    repository = InMemoryUserProfileRepository()
    legacy = _LegacyProfile(user_id="user-legacy", home_city_id="seattle-wa")
    repository._profiles_by_user_id["user-legacy"] = legacy  # type: ignore[assignment]

    profile = repository.get_or_create("user-legacy")

    assert profile.user_id == "user-legacy"
    assert profile.home_city_id == "seattle-wa"
    assert profile.notifications_enabled is True
    assert profile.notifications_paused_until is None


def test_profile_schema_allows_notification_pause_window_values():
    paused_until = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)

    profile = UserProfile(user_id="user-pause", notifications_paused_until=paused_until)

    assert profile.notifications_enabled is True
    assert profile.notifications_paused_until == paused_until
