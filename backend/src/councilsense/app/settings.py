from dataclasses import dataclass
import os
import hashlib
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
class NotificationRetryPolicySettings:
    max_attempts: int
    backoff_seconds: tuple[int, ...]
    jitter_factor: float
    version: str


@dataclass(frozen=True)
class Settings:
    runtime_env: RuntimeEnvironment
    secret_source: SecretSourceKind
    auth_session_secret: str
    supported_city_ids: tuple[str, ...]
    manual_review_confidence_threshold: float
    warn_confidence_threshold: float
    notification_retry_policy: NotificationRetryPolicySettings
    disable_auth_guard: bool
    local_dev_auth_user_id: str
    notification_replay_operator_user_ids: tuple[str, ...]
    notification_replay_allow_permanent_invalid_override: bool
    meeting_detail_legacy_evidence_references_enabled: bool


DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"
DEFAULT_RUNTIME_ENV: RuntimeEnvironment = "local"
DEFAULT_SECRET_SOURCE: SecretSourceKind = "env"
SUPPORTED_RUNTIME_ENVS: tuple[RuntimeEnvironment, ...] = ("local", "aws")
SUPPORTED_SECRET_SOURCES: tuple[SecretSourceKind, ...] = ("env", "aws-secretsmanager")
DEFAULT_SUPPORTED_CITY_IDS = ("seattle-wa",)
DEFAULT_MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_WARN_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_NOTIFICATION_DELIVERY_MAX_ATTEMPTS = 5
DEFAULT_NOTIFICATION_RETRY_BACKOFF_SECONDS = (15, 60, 300, 900, 3600)
DEFAULT_NOTIFICATION_RETRY_JITTER_FACTOR = 0.0
DEFAULT_MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED = True


def _parse_supported_city_ids(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_SUPPORTED_CITY_IDS

    parsed = tuple(city_id.strip() for city_id in raw.split(",") if city_id.strip())
    if not parsed:
        return DEFAULT_SUPPORTED_CITY_IDS
    return parsed


def _parse_string_list(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(value.strip() for value in raw.split(",") if value.strip())


def _parse_optional_str(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _parse_bool(*, raw: str | None, default: bool, env_name: str) -> bool:
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{env_name} must be a boolean (true/false)")


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


def _parse_positive_int(*, raw: str | None, default: int, env_name: str) -> int:
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer > 0") from exc

    if value <= 0:
        raise ValueError(f"{env_name} must be an integer > 0")
    return value


def _parse_backoff_seconds(*, raw: str | None) -> tuple[int, ...]:
    if raw is None:
        return DEFAULT_NOTIFICATION_RETRY_BACKOFF_SECONDS

    parts = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not parts:
        raise ValueError("NOTIFICATION_RETRY_BACKOFF_SECONDS must contain at least one positive integer")

    values: list[int] = []
    for part in parts:
        try:
            value = int(part)
        except ValueError as exc:
            raise ValueError(
                "NOTIFICATION_RETRY_BACKOFF_SECONDS must be a comma-separated list of positive integers"
            ) from exc
        if value <= 0:
            raise ValueError(
                "NOTIFICATION_RETRY_BACKOFF_SECONDS must be a comma-separated list of positive integers"
            )
        values.append(value)

    if any(current < previous for previous, current in zip(values, values[1:])):
        raise ValueError("NOTIFICATION_RETRY_BACKOFF_SECONDS must be monotonic non-decreasing")

    return tuple(values)


def _derive_notification_retry_policy_version(
    *,
    max_attempts: int,
    backoff_seconds: tuple[int, ...],
    jitter_factor: float,
    explicit_version: str | None,
) -> str:
    if explicit_version is not None:
        normalized = explicit_version.strip()
        if not normalized:
            raise ValueError("NOTIFICATION_RETRY_POLICY_VERSION must be non-empty when provided")
        return normalized

    fingerprint_input = f"max={max_attempts}|backoff={','.join(str(value) for value in backoff_seconds)}|jitter={jitter_factor:.6f}"
    digest = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:12]
    return f"notif-retry-v1-{digest}"


def _parse_notification_retry_policy() -> NotificationRetryPolicySettings:
    max_attempts = _parse_positive_int(
        raw=os.getenv("NOTIFICATION_DELIVERY_MAX_ATTEMPTS"),
        default=DEFAULT_NOTIFICATION_DELIVERY_MAX_ATTEMPTS,
        env_name="NOTIFICATION_DELIVERY_MAX_ATTEMPTS",
    )
    backoff_seconds = _parse_backoff_seconds(raw=os.getenv("NOTIFICATION_RETRY_BACKOFF_SECONDS"))
    jitter_factor = _parse_probability_threshold(
        raw=os.getenv("NOTIFICATION_RETRY_JITTER_FACTOR"),
        default=DEFAULT_NOTIFICATION_RETRY_JITTER_FACTOR,
        env_name="NOTIFICATION_RETRY_JITTER_FACTOR",
    )
    version = _derive_notification_retry_policy_version(
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        jitter_factor=jitter_factor,
        explicit_version=os.getenv("NOTIFICATION_RETRY_POLICY_VERSION"),
    )

    return NotificationRetryPolicySettings(
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        jitter_factor=jitter_factor,
        version=version,
    )


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
        notification_retry_policy=_parse_notification_retry_policy(),
        notification_replay_operator_user_ids=_parse_string_list(os.getenv("NOTIFICATION_REPLAY_OPERATOR_USER_IDS")),
        notification_replay_allow_permanent_invalid_override=_parse_bool(
            raw=os.getenv("NOTIFICATION_REPLAY_ALLOW_PERMANENT_INVALID_OVERRIDE"),
            default=False,
            env_name="NOTIFICATION_REPLAY_ALLOW_PERMANENT_INVALID_OVERRIDE",
        ),
        meeting_detail_legacy_evidence_references_enabled=_parse_bool(
            raw=os.getenv("MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED"),
            default=DEFAULT_MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED,
            env_name="MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED",
        ),
        disable_auth_guard=_parse_bool(
            raw=os.getenv("COUNCILSENSE_DISABLE_AUTH_GUARD"),
            default=False,
            env_name="COUNCILSENSE_DISABLE_AUTH_GUARD",
        ),
        local_dev_auth_user_id=_parse_optional_str(os.getenv("COUNCILSENSE_LOCAL_DEV_AUTH_USER_ID"))
        or "local-dev-user",
    )
