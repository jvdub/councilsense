from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


UNSET = object()


@dataclass
class UserProfile:
    user_id: str
    home_city_id: str | None = None
    notifications_enabled: bool = True
    notifications_paused_until: datetime | None = None


class UnsupportedCityError(Exception):
    def __init__(self, home_city_id: str) -> None:
        self.home_city_id = home_city_id
        super().__init__(f"Unsupported home_city_id: {home_city_id}")


class InMemoryUserProfileRepository:
    def __init__(self) -> None:
        self._profiles_by_user_id: dict[str, UserProfile] = {}

    def get_or_create(self, user_id: str) -> UserProfile:
        existing = self._profiles_by_user_id.get(user_id)
        if existing is not None:
            self._ensure_schema_defaults(existing)
            return existing

        created = UserProfile(user_id=user_id)
        self._profiles_by_user_id[user_id] = created
        return created

    def _ensure_schema_defaults(self, profile: UserProfile) -> None:
        if not hasattr(profile, "notifications_enabled"):
            profile.notifications_enabled = True
        if not hasattr(profile, "notifications_paused_until"):
            profile.notifications_paused_until = None

    def set_home_city(self, user_id: str, home_city_id: str) -> UserProfile:
        profile = self.get_or_create(user_id)
        profile.home_city_id = home_city_id
        return profile

    def save(self, profile: UserProfile) -> UserProfile:
        self._profiles_by_user_id[profile.user_id] = profile
        return profile


class UserBootstrapService:
    def __init__(self, repository: InMemoryUserProfileRepository, supported_city_ids: tuple[str, ...]) -> None:
        self._repository = repository
        self._supported_city_ids = supported_city_ids

    def get_bootstrap(self, user_id: str) -> dict:
        profile = self._repository.get_or_create(user_id)
        self._validate_home_city_if_set(profile)
        return self._as_bootstrap_response(profile)

    def set_home_city(self, user_id: str, home_city_id: str) -> dict:
        self._validate_city_id(home_city_id)
        profile = self._repository.set_home_city(user_id, home_city_id)
        return self._as_bootstrap_response(profile)

    def _as_bootstrap_response(self, profile: UserProfile) -> dict:
        return {
            "user_id": profile.user_id,
            "home_city_id": profile.home_city_id,
            "onboarding_required": profile.home_city_id is None,
            "supported_city_ids": list(self._supported_city_ids),
        }

    def _validate_home_city_if_set(self, profile: UserProfile) -> None:
        if profile.home_city_id is None:
            return
        self._validate_city_id(profile.home_city_id)

    def _validate_city_id(self, home_city_id: str) -> None:
        if home_city_id not in self._supported_city_ids:
            raise UnsupportedCityError(home_city_id)


class UserProfileService:
    def __init__(self, repository: InMemoryUserProfileRepository, supported_city_ids: tuple[str, ...]) -> None:
        self._repository = repository
        self._supported_city_ids = supported_city_ids

    def get_profile(self, user_id: str) -> UserProfile:
        profile = self._repository.get_or_create(user_id)
        self._validate_home_city_if_set(profile)
        return profile

    def patch_profile(
        self,
        user_id: str,
        *,
        home_city_id: str | object = UNSET,
        notifications_enabled: bool | object = UNSET,
        notifications_paused_until: datetime | None | object = UNSET,
    ) -> UserProfile:
        profile = self._repository.get_or_create(user_id)

        if home_city_id is not UNSET:
            if not isinstance(home_city_id, str):
                raise UnsupportedCityError(str(home_city_id))
            self._validate_city_id(home_city_id)
            profile.home_city_id = home_city_id

        if notifications_enabled is not UNSET:
            profile.notifications_enabled = bool(notifications_enabled)

        if notifications_paused_until is not UNSET:
            profile.notifications_paused_until = notifications_paused_until

        self._repository.save(profile)
        return profile

    def _validate_home_city_if_set(self, profile: UserProfile) -> None:
        if profile.home_city_id is None:
            return
        self._validate_city_id(profile.home_city_id)

    def _validate_city_id(self, home_city_id: str) -> None:
        if home_city_id not in self._supported_city_ids:
            raise UnsupportedCityError(home_city_id)