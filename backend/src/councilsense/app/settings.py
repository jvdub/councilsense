from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    auth_session_secret: str
    supported_city_ids: tuple[str, ...]


DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"
DEFAULT_SUPPORTED_CITY_IDS = ("seattle-wa",)


def _parse_supported_city_ids(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_SUPPORTED_CITY_IDS

    parsed = tuple(city_id.strip() for city_id in raw.split(",") if city_id.strip())
    if not parsed:
        return DEFAULT_SUPPORTED_CITY_IDS
    return parsed


def get_settings() -> Settings:
    return Settings(
        auth_session_secret=os.getenv("AUTH_SESSION_SECRET", DEFAULT_SESSION_SECRET),
        supported_city_ids=_parse_supported_city_ids(os.getenv("SUPPORTED_CITY_IDS")),
    )
