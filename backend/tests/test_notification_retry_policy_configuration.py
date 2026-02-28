from __future__ import annotations

import pytest

from councilsense.app.notification_delivery_worker import validate_worker_startup_environment
from councilsense.app.settings import get_settings


def test_get_settings_parses_notification_retry_policy_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SESSION_SECRET", "dev-secret")
    monkeypatch.setenv("NOTIFICATION_DELIVERY_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("NOTIFICATION_RETRY_BACKOFF_SECONDS", "5,10,30")
    monkeypatch.setenv("NOTIFICATION_RETRY_JITTER_FACTOR", "0.25")
    monkeypatch.setenv("NOTIFICATION_RETRY_POLICY_VERSION", "ops-policy-2026-02-28")

    settings = get_settings(service_name="worker")

    assert settings.notification_retry_policy.max_attempts == 7
    assert settings.notification_retry_policy.backoff_seconds == (5, 10, 30)
    assert settings.notification_retry_policy.jitter_factor == 0.25
    assert settings.notification_retry_policy.version == "ops-policy-2026-02-28"


def test_worker_startup_rejects_invalid_notification_retry_policy_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SESSION_SECRET", "dev-secret")

    monkeypatch.setenv("NOTIFICATION_DELIVERY_MAX_ATTEMPTS", "0")
    with pytest.raises(ValueError, match="NOTIFICATION_DELIVERY_MAX_ATTEMPTS must be an integer > 0"):
        validate_worker_startup_environment()

    monkeypatch.setenv("NOTIFICATION_DELIVERY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("NOTIFICATION_RETRY_BACKOFF_SECONDS", "10,5")
    with pytest.raises(ValueError, match="NOTIFICATION_RETRY_BACKOFF_SECONDS must be monotonic non-decreasing"):
        validate_worker_startup_environment()

    monkeypatch.setenv("NOTIFICATION_RETRY_BACKOFF_SECONDS", "5,10")
    monkeypatch.setenv("NOTIFICATION_RETRY_JITTER_FACTOR", "1.2")
    with pytest.raises(ValueError, match=r"NOTIFICATION_RETRY_JITTER_FACTOR must be a float in \[0.0, 1.0\]"):
        validate_worker_startup_environment()
