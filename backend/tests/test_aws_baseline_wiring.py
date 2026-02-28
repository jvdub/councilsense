from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_template() -> dict[str, Any]:
    template_path = _repo_root() / "infra" / "aws" / "staging-baseline.json"
    return json.loads(template_path.read_text(encoding="utf-8"))


def _load_workflow() -> str:
    workflow_path = _repo_root() / ".github" / "workflows" / "deploy-aws-staging-baseline.yml"
    return workflow_path.read_text(encoding="utf-8")


def _resource(template: dict[str, Any], logical_name: str) -> dict[str, Any]:
    resources = template["Resources"]
    return resources[logical_name]


def _runtime_environment_variables(service: dict[str, Any]) -> dict[str, Any]:
    variables = (
        service["Properties"]["SourceConfiguration"]["ImageRepository"]["ImageConfiguration"][
            "RuntimeEnvironmentVariables"
        ]
    )
    return {item["Name"]: item["Value"] for item in variables}


def _runtime_environment_secrets(service: dict[str, Any]) -> dict[str, Any]:
    secrets = (
        service["Properties"]["SourceConfiguration"]["ImageRepository"]["ImageConfiguration"][
            "RuntimeEnvironmentSecrets"
        ]
    )
    return {item["Name"]: item["Value"] for item in secrets}


def test_template_defines_baseline_resource_coverage_for_st012_04() -> None:
    template = _load_template()
    resources = template["Resources"]

    assert "BaselineApiService" in resources
    assert "BaselineWorkerService" in resources
    assert "BaselineQueue" in resources
    assert "BaselineDeadLetterQueue" in resources
    assert "BaselineArtifactsBucket" in resources
    assert "BaselineDatabase" in resources
    assert "BaselineSessionSecret" in resources
    assert "FrontendHostingStub" in resources


def test_template_binds_environment_contract_for_api_and_worker() -> None:
    template = _load_template()

    api_service = _resource(template, "BaselineApiService")
    worker_service = _resource(template, "BaselineWorkerService")

    for service in (api_service, worker_service):
        env_vars = _runtime_environment_variables(service)
        assert env_vars["COUNCILSENSE_RUNTIME_ENV"] == "aws"
        assert env_vars["COUNCILSENSE_SECRET_SOURCE"] == "aws-secretsmanager"
        assert "SUPPORTED_CITY_IDS" in env_vars
        assert "MANUAL_REVIEW_CONFIDENCE_THRESHOLD" in env_vars
        assert "WARN_CONFIDENCE_THRESHOLD" in env_vars

        env_secrets = _runtime_environment_secrets(service)
        assert "AUTH_SESSION_SECRET" in env_secrets


def test_template_wires_queue_storage_database_and_telemetry_bindings() -> None:
    template = _load_template()

    for service_name in ("BaselineApiService", "BaselineWorkerService"):
        service = _resource(template, service_name)
        env_vars = _runtime_environment_variables(service)

        assert "COUNCILSENSE_QUEUE_URL" in env_vars
        assert "COUNCILSENSE_STORAGE_BUCKET" in env_vars
        assert "COUNCILSENSE_DATABASE_ENDPOINT" in env_vars
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env_vars

        otel_resource_attributes = env_vars["OTEL_RESOURCE_ATTRIBUTES"]
        assert isinstance(otel_resource_attributes, str)
        assert "deployment.environment=aws" in otel_resource_attributes


def test_staging_pipeline_entrypoint_targets_baseline_deploy_script() -> None:
    workflow = _load_workflow()

    assert "workflow_dispatch" in workflow
    assert "scripts/deploy_aws_staging_baseline.sh" in workflow
    assert "IMAGE_IDENTIFIER_API" in workflow
    assert "IMAGE_IDENTIFIER_WORKER" in workflow
    assert "RDS_MASTER_USER_PASSWORD" in workflow
