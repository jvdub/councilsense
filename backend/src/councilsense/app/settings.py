from dataclasses import dataclass
import os
from typing import Literal, Mapping, Protocol


RuntimeEnvironment = Literal["local", "aws"]
SecretSourceKind = Literal["env", "aws-secretsmanager"]


class SecretSource(Protocol):
    def get_secret(self, key: str) -> str | None: ...


class EnvironmentSecretSource:
    def get_secret(self, key: str) -> str | None:
        return os.getenv(key)


class MappingSecretSource:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = values

    def get_secret(self, key: str) -> str | None:
        return self._values.get(key)


@dataclass(frozen=True)
class Settings:
    runtime_env: RuntimeEnvironment
    secret_source: SecretSourceKind
    auth_session_secret: str
    supported_city_ids: tuple[str, ...]
    manual_review_confidence_threshold: float
    warn_confidence_threshold: float


DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"
DEFAULT_RUNTIME_ENV: RuntimeEnvironment = "local"
DEFAULT_SECRET_SOURCE: SecretSourceKind = "env"
SUPPORTED_RUNTIME_ENVS: tuple[RuntimeEnvironment, ...] = ("local", "aws")
SUPPORTED_SECRET_SOURCES: tuple[SecretSourceKind, ...] = ("env", "aws-secretsmanager")
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


def _parse_runtime_env(raw: str | None) -> RuntimeEnvironment:
    runtime_env = (raw or DEFAULT_RUNTIME_ENV).strip().lower()
    if runtime_env not in SUPPORTED_RUNTIME_ENVS:
        supported = ", ".join(SUPPORTED_RUNTIME_ENVS)
        raise ValueError(f"COUNCILSENSE_RUNTIME_ENV must be one of: {supported}")
    return runtime_env  # type: ignore[return-value]


def _parse_secret_source(raw: str | None) -> SecretSourceKind:
    source = (raw or DEFAULT_SECRET_SOURCE).strip().lower()
    if source not in SUPPORTED_SECRET_SOURCES:
        supported = ", ".join(SUPPORTED_SECRET_SOURCES)
        raise ValueError(f"COUNCILSENSE_SECRET_SOURCE must be one of: {supported}")
    return source  # type: ignore[return-value]


def _resolve_auth_session_secret(*, runtime_env: RuntimeEnvironment, source: SecretSource, service_name: str) -> str:
    secret = source.get_secret("AUTH_SESSION_SECRET")
    if secret is None:
        if runtime_env == "aws":
            raise ValueError(
                f"AUTH_SESSION_SECRET is required for service={service_name} when "
                "COUNCILSENSE_RUNTIME_ENV=aws; configure it through the selected secret source"
            )
        return DEFAULT_SESSION_SECRET

    resolved = secret.strip()
    if not resolved:
        raise ValueError("AUTH_SESSION_SECRET must be non-empty")
    if runtime_env == "aws" and resolved == DEFAULT_SESSION_SECRET:
        raise ValueError(
            "AUTH_SESSION_SECRET must not use the development default when "
            "COUNCILSENSE_RUNTIME_ENV=aws"
        )
    return resolved


def get_settings(*, service_name: Literal["api", "worker"] = "api", secret_source: SecretSource | None = None) -> Settings:
    runtime_env = _parse_runtime_env(os.getenv("COUNCILSENSE_RUNTIME_ENV"))
    selected_secret_source = _parse_secret_source(os.getenv("COUNCILSENSE_SECRET_SOURCE"))
    source = secret_source or EnvironmentSecretSource()

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

    auth_session_secret = _resolve_auth_session_secret(
        runtime_env=runtime_env,
        source=source,
        service_name=service_name,
    )

    return Settings(
        runtime_env=runtime_env,
        secret_source=selected_secret_source,
        auth_session_secret=auth_session_secret,
        supported_city_ids=_parse_supported_city_ids(os.getenv("SUPPORTED_CITY_IDS")),
        manual_review_confidence_threshold=manual_review_confidence_threshold,
        warn_confidence_threshold=warn_confidence_threshold,
    )
