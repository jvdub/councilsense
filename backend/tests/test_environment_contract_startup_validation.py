from __future__ import annotations

import pytest

from councilsense.app.main import create_app
from councilsense.app.notification_delivery_worker import validate_worker_startup_environment
from councilsense.app.settings import (
    DEFAULT_MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED,
    DEFAULT_ST022_API_ADDITIVE_V1_FIELDS_ENABLED,
    DEFAULT_SESSION_SECRET,
    MappingSecretSource,
    get_settings,
)


def test_local_runtime_uses_safe_defaults_for_api_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COUNCILSENSE_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("COUNCILSENSE_SECRET_SOURCE", raising=False)
    monkeypatch.delenv("AUTH_SESSION_SECRET", raising=False)

    settings = get_settings(service_name="api")

    assert settings.runtime_env == "local"
    assert settings.secret_source == "env"
    assert settings.auth_session_secret == DEFAULT_SESSION_SECRET
    assert (
        settings.meeting_detail_legacy_evidence_references_enabled
        == DEFAULT_MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED
    )
    assert settings.meeting_detail_additive_api.enabled == DEFAULT_ST022_API_ADDITIVE_V1_FIELDS_ENABLED
    assert settings.meeting_detail_additive_api.enabled_blocks == ()


def test_meeting_detail_legacy_evidence_flag_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED", "false")

    settings = get_settings(service_name="api")

    assert settings.meeting_detail_legacy_evidence_references_enabled is False


def test_st022_additive_api_blocks_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")

    settings = get_settings(service_name="api")

    assert settings.meeting_detail_additive_api.enabled is True
    assert settings.meeting_detail_additive_api.enabled_blocks == (
        "planned",
        "outcomes",
        "planned_outcome_mismatches",
    )


def test_st022_additive_api_blocks_require_master_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "false")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned")

    with pytest.raises(ValueError, match="ST022_API_ADDITIVE_V1_BLOCKS must be empty unless"):
        get_settings(service_name="api")


def test_st022_additive_api_blocks_require_explicit_allow_list_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.delenv("ST022_API_ADDITIVE_V1_BLOCKS", raising=False)

    with pytest.raises(ValueError, match="must explicitly allow one or more blocks"):
        get_settings(service_name="api")


def test_st022_additive_api_mismatches_require_planned_and_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned_outcome_mismatches")

    with pytest.raises(ValueError, match="cannot enable planned_outcome_mismatches without planned and outcomes"):
        get_settings(service_name="api")


def test_aws_runtime_requires_auth_session_secret_for_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "aws")
    monkeypatch.delenv("AUTH_SESSION_SECRET", raising=False)

    with pytest.raises(ValueError, match="AUTH_SESSION_SECRET is required"):
        create_app()


def test_aws_runtime_rejects_development_default_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "aws")
    monkeypatch.setenv("AUTH_SESSION_SECRET", DEFAULT_SESSION_SECRET)

    with pytest.raises(ValueError, match="must not use the development default"):
        get_settings(service_name="api")


def test_contract_rejects_invalid_runtime_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "staging")

    with pytest.raises(ValueError, match="COUNCILSENSE_RUNTIME_ENV must be one of"):
        get_settings(service_name="api")


def test_worker_startup_smoke_passes_for_aws_like_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "aws")
    monkeypatch.setenv("COUNCILSENSE_SECRET_SOURCE", "aws-secretsmanager")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "worker-secret")

    validate_worker_startup_environment()


def test_secret_source_abstraction_allows_non_env_secret_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "aws")
    monkeypatch.setenv("COUNCILSENSE_SECRET_SOURCE", "aws-secretsmanager")
    monkeypatch.delenv("AUTH_SESSION_SECRET", raising=False)

    settings = get_settings(
        service_name="api",
        secret_source=MappingSecretSource({"AUTH_SESSION_SECRET": "from-secret-provider"}),
    )

    assert settings.auth_session_secret == "from-secret-provider"
