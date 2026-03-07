from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_st029_pipeline_recovery_runbook_requires_actor_reason_and_idempotency() -> None:
    runbook_path = _repo_root() / "docs" / "runbooks" / "st-029-pipeline-dlq-contract.md"
    content = runbook_path.read_text(encoding="utf-8")

    assert "## Operator Recovery Workflow" in content
    assert "actor_user_id" in content
    assert "replay_reason" in content
    assert "idempotency_key" in content
    assert "pipeline_replay_audit_events" in content
    assert "pipeline_replay_execution" in content
    assert "pipeline_replay_command" in content
    assert "publish_stage_outcome_already_materialized" in content
    assert "replayed" in content and "noop" in content