from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    auth_session_secret: str
    supported_city_ids: tuple[str, ...]
    manual_review_confidence_threshold: float
    warn_confidence_threshold: float


DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"
DEFAULT_SUPPORTED_CITY_IDS = ("seattle-wa",)
DEFAULT_MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_WARN_CONFIDENCE_THRESHOLD = 0.8


def _parse_supported_city_ids(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_SUPPORTED_CITY_IDS

    parsed = tuple(city_id.strip() for city_id in raw.split(",") if city_id.strip())
    if not parsed:
        return DEFAULT_SUPPORTED_CITY_IDS
    return parsed


def _parse_probability_threshold(*, raw: str | None, default: float, env_name: str) -> float:
    if raw is None:
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a float in [0.0, 1.0]") from exc

    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{env_name} must be a float in [0.0, 1.0]")
    return value


def get_settings() -> Settings:
    manual_review_confidence_threshold = _parse_probability_threshold(
        raw=os.getenv("MANUAL_REVIEW_CONFIDENCE_THRESHOLD"),
        default=DEFAULT_MANUAL_REVIEW_CONFIDENCE_THRESHOLD,
        env_name="MANUAL_REVIEW_CONFIDENCE_THRESHOLD",
    )
    warn_confidence_threshold = _parse_probability_threshold(
        raw=os.getenv("WARN_CONFIDENCE_THRESHOLD"),
        default=DEFAULT_WARN_CONFIDENCE_THRESHOLD,
        env_name="WARN_CONFIDENCE_THRESHOLD",
    )
    if warn_confidence_threshold < manual_review_confidence_threshold:
        raise ValueError(
            "WARN_CONFIDENCE_THRESHOLD must be greater than or equal to "
            "MANUAL_REVIEW_CONFIDENCE_THRESHOLD"
        )

    return Settings(
        auth_session_secret=os.getenv("AUTH_SESSION_SECRET", DEFAULT_SESSION_SECRET),
        supported_city_ids=_parse_supported_city_ids(os.getenv("SUPPORTED_CITY_IDS")),
        manual_review_confidence_threshold=manual_review_confidence_threshold,
        warn_confidence_threshold=warn_confidence_threshold,
    )
