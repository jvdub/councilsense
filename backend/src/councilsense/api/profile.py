from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserProfile:
    user_id: str
    home_city_id: str | None = None


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
            return existing

        created = UserProfile(user_id=user_id)
        self._profiles_by_user_id[user_id] = created
        return created

    def set_home_city(self, user_id: str, home_city_id: str) -> UserProfile:
        profile = self.get_or_create(user_id)
        profile.home_city_id = home_city_id
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