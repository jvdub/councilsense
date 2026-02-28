from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_release_parity_checklist_covers_reliability_idempotency_telemetry_and_differences() -> None:
    checklist_path = _repo_root() / "docs" / "runbooks" / "st-012-behavior-parity-checklist.md"

    assert checklist_path.exists()

    content = checklist_path.read_text(encoding="utf-8")

    assert "## Release record" in content
    assert "## Reliability parity" in content
    assert "## Idempotency parity" in content
    assert "## Observability parity" in content
    assert "## Known acceptable environment differences" in content


def test_deployment_and_rollback_runbook_covers_local_and_aws_paths() -> None:
    runbook_path = _repo_root() / "docs" / "runbooks" / "st-012-deployment-and-rollback-runbook.md"

    assert runbook_path.exists()

    content = runbook_path.read_text(encoding="utf-8")

    assert "## Local path" in content
    assert "### Deploy" in content
    assert "### Rollback" in content
    assert "docker compose -f docker-compose.local.yml" in content
    assert "./scripts/local_runtime_smoke.sh" in content

    assert "## AWS staging path" in content
    assert ".github/workflows/deploy-aws-staging-baseline.yml" in content
    assert "bash ./scripts/deploy_aws_staging_baseline.sh" in content
    assert "aws cloudformation describe-stacks" in content


def test_parity_ci_workflow_runs_core_contract_checks() -> None:
    workflow_path = _repo_root() / ".github" / "workflows" / "st012-parity-contract-checks.yml"

    assert workflow_path.exists()

    content = workflow_path.read_text(encoding="utf-8")

    assert "name: ST-012 Parity Contract Checks" in content
    assert "pull_request" in content
    assert "workflow_dispatch" in content
    assert "test_environment_contract_startup_validation.py" in content
    assert "test_aws_baseline_wiring.py" in content
    assert "test_st012_local_runtime_compose_smoke_flow.py" in content
    assert "test_st012_parity_ci_and_deployment_docs.py" in content
