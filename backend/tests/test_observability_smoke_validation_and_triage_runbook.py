from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_st011_smoke_and_triage_artifacts_exist() -> None:
    runbook_dir = _repo_root() / "docs" / "runbooks"

    smoke_checklist = runbook_dir / "st-011-smoke-validation-checklist.md"
    triage_runbook = runbook_dir / "st-011-triage-runbook.md"
    rehearsal_evidence = runbook_dir / "st-011-smoke-rehearsal-evidence.md"

    assert smoke_checklist.exists()
    assert triage_runbook.exists()
    assert rehearsal_evidence.exists()


def test_st011_smoke_checklist_covers_non_local_telemetry_presence_and_evidence_retention() -> None:
    checklist_path = _repo_root() / "docs" / "runbooks" / "st-011-smoke-validation-checklist.md"
    content = checklist_path.read_text(encoding="utf-8")

    assert "# ST-011 Smoke Validation Checklist (Non-Local)" in content
    assert "environment" in content
    assert "aws" in content
    assert "pipeline-stage-outcomes" in content
    assert "notification-delivery-outcomes" in content
    assert "source-freshness-and-failure-snapshot" in content
    assert "pipeline_stage_finished" in content
    assert "notification_delivery_attempt" in content
    assert "## Evidence Retention Location" in content
    assert "docs/runbooks/st-011-smoke-rehearsal-evidence.md" in content


def test_st011_triage_runbook_maps_failure_modes_to_dashboard_panels_and_log_queries() -> None:
    runbook_path = _repo_root() / "docs" / "runbooks" / "st-011-triage-runbook.md"
    content = runbook_path.read_text(encoding="utf-8")

    assert "## Failure Mode 1: Pipeline Stage Failure" in content
    assert "## Failure Mode 2: Notification Delivery Failure" in content
    assert "## Failure Mode 3: Stale or Failing Source" in content

    assert "pipeline-stage-outcomes" in content
    assert "notification-delivery-outcomes" in content
    assert "source-freshness-and-failure-snapshot" in content

    assert "pipeline_stage_error" in content
    assert "notification_delivery_attempt" in content
    assert "event.stage = \"ingest\"" in content


def test_st011_rehearsal_evidence_documents_end_to_end_runbook_execution() -> None:
    evidence_path = _repo_root() / "docs" / "runbooks" / "st-011-smoke-rehearsal-evidence.md"
    content = evidence_path.read_text(encoding="utf-8")

    assert "# ST-011 Smoke + Triage Rehearsal Evidence" in content
    assert "Task: TASK-ST-011-05" in content
    assert "Pipeline stage failure triage" in content
    assert "Notification delivery failure triage" in content
    assert "Stale/failing source triage" in content
    assert "PASS" in content
