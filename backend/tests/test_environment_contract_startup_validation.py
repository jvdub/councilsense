from __future__ import annotations

import sqlite3
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.app.notification_delivery_worker import validate_worker_startup_environment
from councilsense.app.settings import (
    DEFAULT_MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED,
    DEFAULT_ON_DEMAND_PROCESSING_MAX_ACTIVE_REQUESTS_PER_USER,
    DEFAULT_ON_DEMAND_PROCESSING_MAX_QUEUED_REQUESTS_PER_USER,
    DEFAULT_ST022_API_ADDITIVE_V1_FIELDS_ENABLED,
    DEFAULT_ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED,
    DEFAULT_ST035_API_FOLLOW_UP_PROMPTS_ENABLED,
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
    assert (
        settings.meeting_detail_resident_relevance_api.enabled
        == DEFAULT_ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED
    )
    assert (
        settings.meeting_detail_follow_up_prompts_api.enabled
        == DEFAULT_ST035_API_FOLLOW_UP_PROMPTS_ENABLED
    )
    assert (
        settings.on_demand_processing_admission_control.max_active_requests_per_user
        == DEFAULT_ON_DEMAND_PROCESSING_MAX_ACTIVE_REQUESTS_PER_USER
    )
    assert (
        settings.on_demand_processing_admission_control.max_queued_requests_per_user
        == DEFAULT_ON_DEMAND_PROCESSING_MAX_QUEUED_REQUESTS_PER_USER
    )


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


def test_st033_resident_relevance_api_flag_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED", "true")

    settings = get_settings(service_name="api")

    assert settings.meeting_detail_resident_relevance_api.enabled is True


def test_st035_follow_up_prompts_api_flag_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "true")

    settings = get_settings(service_name="api")

    assert settings.meeting_detail_follow_up_prompts_api.enabled is True


def test_on_demand_processing_limits_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ON_DEMAND_PROCESSING_ACTIVE_REQUESTS_PER_USER_LIMIT", "7")
    monkeypatch.setenv("ON_DEMAND_PROCESSING_QUEUED_REQUESTS_PER_USER_LIMIT", "4")

    settings = get_settings(service_name="api")

    assert settings.on_demand_processing_admission_control.max_active_requests_per_user == 7
    assert settings.on_demand_processing_admission_control.max_queued_requests_per_user == 4


def test_on_demand_processing_active_limit_must_not_be_lower_than_queued_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ON_DEMAND_PROCESSING_ACTIVE_REQUESTS_PER_USER_LIMIT", "1")
    monkeypatch.setenv("ON_DEMAND_PROCESSING_QUEUED_REQUESTS_PER_USER_LIMIT", "2")

    with pytest.raises(ValueError, match="must be greater than or equal to"):
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


def test_api_startup_discovers_meetings_for_supported_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    def _stub_fetch(url: str, _: float) -> bytes:
        if "/Events?" in url or "/events?" in url:
            return (
                '{"value":[{"id":71,"eventName":"City Council Meeting","eventDate":"2026-03-10T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}]}'
            ).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b'<a href="/event/71/files">Event 71</a>'
        if "/Events/71" in url:
            return (
                '{"id":71,"eventName":"City Council Meeting","eventDate":"2026-03-10T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}'
            ).encode("utf-8")
        return b'{"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}'

    monkeypatch.setenv("SUPPORTED_CITY_IDS", "city-eagle-mountain-ut")
    monkeypatch.setenv("COUNCILSENSE_SQLITE_PATH", "startup-discovery-success.sqlite")
    monkeypatch.setattr("councilsense.app.discovery_sync._fetch_url_bytes", _stub_fetch)

    with TestClient(create_app()) as client:
        app = cast(Any, client.app)
        discovered_count = app.state.db_connection.execute(
            "SELECT COUNT(*) FROM discovered_meetings"
        ).fetchone()[0]

        assert discovered_count == 1
        assert app.state.discovery_startup_sync is not None
        assert app.state.discovery_startup_sync.synced_count == 1
        assert app.state.discovery_startup_sync.errors == ()
        app.state.db_connection.close()

    sqlite3.connect("startup-discovery-success.sqlite").close()


def test_api_startup_discovery_failure_does_not_block_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failing_fetch(_: str, __: float) -> bytes:
        raise RuntimeError("source unavailable")

    monkeypatch.setenv("SUPPORTED_CITY_IDS", "city-eagle-mountain-ut")
    monkeypatch.setenv("COUNCILSENSE_SQLITE_PATH", "startup-discovery-failure.sqlite")
    monkeypatch.setattr("councilsense.app.discovery_sync._fetch_url_bytes", _failing_fetch)

    with TestClient(create_app()) as client:
        app = cast(Any, client.app)
        discovered_count = app.state.db_connection.execute(
            "SELECT COUNT(*) FROM discovered_meetings"
        ).fetchone()[0]

        assert discovered_count == 0
        assert app.state.discovery_startup_sync is not None
        assert app.state.discovery_startup_sync.synced_count == 0
        assert any("source_id=source-eagle-mountain-ut-minutes-primary" in error for error in app.state.discovery_startup_sync.errors)
        app.state.db_connection.close()

    sqlite3.connect("startup-discovery-failure.sqlite").close()


def test_api_startup_discovery_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    def _flaky_fetch(url: str, _: float) -> bytes:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary source failure")
        if "/Events?" in url or "/events?" in url:
            return (
                '{"value":[{"id":71,"eventName":"City Council Meeting","eventDate":"2026-03-10T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}]}'
            ).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b'<a href="/event/71/files">Event 71</a>'
        if "/Events/71" in url:
            return (
                '{"id":71,"eventName":"City Council Meeting","eventDate":"2026-03-10T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}'
            ).encode("utf-8")
        return b'{"publishedFiles":[{"type":"Minutes","name":"Minutes","url":"stream/71-minutes.pdf"}]}'

    monkeypatch.setenv("SUPPORTED_CITY_IDS", "city-eagle-mountain-ut")
    monkeypatch.setenv("COUNCILSENSE_SQLITE_PATH", "startup-discovery-retry.sqlite")
    monkeypatch.setattr("councilsense.app.discovery_sync._fetch_url_bytes", _flaky_fetch)

    with TestClient(create_app()) as client:
        app = cast(Any, client.app)
        discovered_count = app.state.db_connection.execute(
            "SELECT COUNT(*) FROM discovered_meetings"
        ).fetchone()[0]

        assert discovered_count == 1
        assert app.state.discovery_startup_sync is not None
        assert app.state.discovery_startup_sync.synced_count == 1
        assert app.state.discovery_startup_sync.errors == ()
        assert attempts["count"] >= 2
        app.state.db_connection.close()

    sqlite3.connect("startup-discovery-retry.sqlite").close()
