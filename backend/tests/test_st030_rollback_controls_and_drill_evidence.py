from __future__ import annotations

import json
from pathlib import Path

from councilsense.app.quality_gate_rollout import (
    ROLLBACK_CONTROL_PLAN_SCHEMA_VERSION,
    build_document_aware_rollback_plan,
    build_rollback_sequence,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_st030_document_aware_rollback_plan_supports_report_only_reversion_and_full_disable() -> None:
    plan = build_document_aware_rollback_plan()
    payload = plan.to_payload()

    assert payload["schema_version"] == ROLLBACK_CONTROL_PLAN_SCHEMA_VERSION
    assert payload["schema_rollback_required"] is False

    profiles = {profile["profile_id"]: profile for profile in payload["profiles"]}
    assert set(profiles) == {"report_only_reversion", "full_disable_after_report_only"}

    report_only_profile = profiles["report_only_reversion"]
    assert report_only_profile["steps"] == [
        {
            "step": 1,
            "control": "gate_mode",
            "action": "set_report_only",
            "pre_check": "Confirm the affected environment/cohort currently resolves gate_mode=enforced and capture the latest promotion artifact plus shadow diagnostics run IDs for the incident record.",
            "post_check": "Publish metadata reports gate_mode=report_only and enforcement_outcome.decision=observe for the next verification run.",
            "resulting_mode": "report_only",
        }
    ]

    full_disable_profile = profiles["full_disable_after_report_only"]
    assert [step["control"] for step in full_disable_profile["steps"]] == [
        "specificity_retention_enabled",
        "evidence_projection_enabled",
        "topic_hardening_enabled",
    ]

    escalation_policy = payload["escalation_policy"]
    assert escalation_policy["primary_owner"] == "platform/backend on-call"
    assert escalation_policy["secondary_owner"] == "release owner"
    assert escalation_policy["escalation_owner"] == "incident commander"
    assert escalation_policy["paging_route"] == [
        "platform/backend on-call",
        "release owner",
        "incident commander",
    ]


def test_st030_legacy_rollback_sequence_keeps_reverse_order_and_adds_step_checks() -> None:
    sequence = build_rollback_sequence()

    assert [row["control"] for row in sequence] == [
        "specificity_retention_enabled",
        "evidence_projection_enabled",
        "topic_hardening_enabled",
        "gate_mode",
    ]
    assert all("pre_check" in row and "post_check" in row and "resulting_mode" in row for row in sequence)
    assert sequence[-1]["resulting_mode"] == "report_only"


def test_st030_rollback_runbook_and_sample_evidence_cover_ownership_and_drill_outputs() -> None:
    repo_root = _repo_root()
    runbook_path = repo_root / "docs" / "runbooks" / "st-030-rollback-controls-and-drill-evidence.md"
    evidence_path = repo_root / "docs" / "runbooks" / "st-030-promotion-rollback-drill-evidence.sample.json"

    assert runbook_path.exists()
    assert evidence_path.exists()

    content = runbook_path.read_text(encoding="utf-8")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert "## Ownership And Escalation" in content
    assert "## Promotion Pre-Checks" in content
    assert "## Rollback Profile: Report-Only Reversion" in content
    assert "## Rollback Profile: Full Disable After Report-Only" in content
    assert "## Drill Procedure" in content
    assert "## Required Evidence Package" in content

    assert payload["schema_version"] == "st-030-promotion-rollback-drill-evidence-v1"
    assert payload["task_id"] == "TASK-ST-030-05"
    assert payload["ownership"]["paging_route"] == [
        "platform/backend on-call",
        "release owner",
        "incident commander",
    ]
    assert payload["promotion_precheck"]["eligible"] is True
    assert payload["promotion_precheck"]["required_consecutive_green_runs"] == 2
    assert [action["control"] for action in payload["actions"]] == [
        "gate_mode",
        "gate_mode",
        "specificity_retention_enabled",
        "evidence_projection_enabled",
        "topic_hardening_enabled",
    ]
    assert payload["post_checks"]["baseline_publish_behavior_restored"] is True
    assert payload["post_checks"]["schema_rollback_required"] is False
    assert payload["escalation"]["status"] == "not_invoked"