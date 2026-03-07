from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_ruleset() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-031-source-aware-alert-rules.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_fixture() -> dict[str, Any]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st031_alert_policy_validation.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_evidence() -> dict[str, Any]:
    path = _repo_root() / "docs" / "runbooks" / "st-031-staging-alert-simulation-evidence.sample.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_st031_staging_evidence_artifacts_exist() -> None:
    repo_root = _repo_root()

    assert (repo_root / "docs" / "runbooks" / "st-031-staging-alert-simulation-evidence.md").exists()
    assert (repo_root / "docs" / "runbooks" / "st-031-staging-alert-simulation-evidence.sample.json").exists()


def test_st031_staging_simulation_bundle_covers_required_alert_classes_and_repeatable_inputs() -> None:
    ruleset = _load_ruleset()
    fixture = _load_fixture()
    evidence = _load_evidence()

    assert evidence["schema_version"] == "st-031-staging-alert-simulation-evidence-v1"
    assert evidence["task_id"] == "TASK-ST-031-05"
    assert evidence["environment"] == "staging"
    assert evidence["overall_result"] == "pass_with_follow_up_actions"
    assert cast(dict[str, Any], evidence["release_readiness"])["status"] == "ready_with_follow_up_actions"
    assert cast(dict[str, Any], evidence["release_readiness"])["blocking_issues"] == 0

    scenarios = cast(list[dict[str, Any]], evidence["scenarios"])
    assert {cast(str, scenario["alert_class"]) for scenario in scenarios} == {
        "parser_drift_spike",
        "missing_minutes_surge",
        "summarize_failure_spike",
        "stale_pipeline_dlq_backlog",
    }

    fixture_scenarios = {
        cast(str, scenario["scenario_id"]): cast(dict[str, Any], scenario)
        for scenario in cast(list[dict[str, Any]], fixture["scenarios"])
    }
    rules_by_id = {
        cast(str, rule["alert_id"]): cast(dict[str, Any], rule)
        for rule in cast(list[dict[str, Any]], ruleset["rules"])
    }

    for scenario in scenarios:
        fixture_scenario = fixture_scenarios[cast(str, scenario["fixture_scenario_id"])]
        selected_alert_id = cast(str, scenario["selected_alert_id"])
        selected_rule = rules_by_id[selected_alert_id]

        assert cast(str, scenario["severity"]) == cast(str, selected_rule["severity"])
        assert cast(str, scenario["alert_class"]) == cast(str, selected_rule["alert_class"])
        assert cast(str, scenario["simulation_method"])

        repeatable_artifacts = cast(list[str], scenario["repeatable_artifacts"])
        assert repeatable_artifacts
        for artifact in repeatable_artifacts:
            assert (_repo_root() / artifact).exists(), artifact

        expected_alert_ids = set(cast(list[str], fixture_scenario["expected_alert_ids"]))
        trigger_result = cast(dict[str, Any], scenario["trigger_result"])
        assert cast(str, trigger_result["status"]) == "fired"
        assert set(cast(list[str], trigger_result["fired_alert_ids"])) == expected_alert_ids
        assert float(trigger_result["observed_value"]) >= float(trigger_result["threshold_value"])
        assert _parse_datetime(cast(str, trigger_result["triggered_at_utc"]))

        route_result = cast(dict[str, Any], scenario["route_result"])
        owner_routing = cast(dict[str, Any], selected_rule["owner_routing"])
        assert cast(str, route_result["status"]) == "delivered"
        assert cast(str, route_result["delivery_channel"]) == "ops-multi-document-alerts"
        assert cast(str, route_result["primary_role"]) == cast(str, owner_routing["primary_role"])
        assert cast(str, route_result["secondary_role"]) == cast(str, owner_routing["secondary_role"])
        assert cast(str, route_result["escalate_to"]) == cast(str, owner_routing["escalate_to"])

        ack_result = cast(dict[str, Any], scenario["ack_result"])
        assert cast(str, ack_result["status"]) == "acknowledged"
        assert cast(str, ack_result["acknowledged_by"])
        assert cast(str, ack_result["acknowledgment_note"])
        ack_at = _parse_datetime(cast(str, ack_result["acknowledged_at_utc"]))
        assert ack_at >= _parse_datetime(cast(str, trigger_result["triggered_at_utc"]))

        escalation_result = cast(dict[str, Any], scenario["escalation_result"])
        escalation_status = cast(str, escalation_result["status"])
        assert escalation_status in {"escalated", "not_required"}
        if escalation_status == "escalated":
            assert cast(str, escalation_result["escalated_to"]) == cast(str, owner_routing["escalate_to"])
            assert _parse_datetime(cast(str, escalation_result["escalated_at_utc"])) >= ack_at
        else:
            assert cast(str, escalation_result["reason"])

        walkthrough = cast(dict[str, Any], scenario["walkthrough_result"])
        assert cast(str, walkthrough["runbook"]) == cast(str, selected_rule["runbook"])
        assert cast(str, walkthrough["result"]) == "completed"
        assert cast(str, walkthrough["remediation_outcome"])
        assert cast(str, walkthrough["closure_status"])
        assert _parse_datetime(cast(str, walkthrough["started_at_utc"])) >= ack_at
        assert _parse_datetime(cast(str, walkthrough["completed_at_utc"])) >= _parse_datetime(cast(str, walkthrough["started_at_utc"]))

        responders = cast(list[str], walkthrough["responders"])
        assert responders
        supporting_paths = cast(list[str], walkthrough["supporting_paths"])
        for path_value in supporting_paths:
            assert (_repo_root() / path_value).exists(), path_value
        assert cast(list[str], walkthrough["follow_up_action_ids"])


def test_st031_follow_up_action_register_is_assigned_time_bound_and_linked() -> None:
    evidence = _load_evidence()

    execution_date = date.fromisoformat(cast(str, evidence["execution_date"]))
    scenarios = cast(list[dict[str, Any]], evidence["scenarios"])
    scenario_ids = {cast(str, scenario["scenario_id"]) for scenario in scenarios}
    actions = cast(list[dict[str, Any]], evidence["follow_up_actions"])

    assert len(actions) == 4
    assert len({cast(str, action["action_id"]) for action in actions}) == len(actions)

    covered_scenarios = set()
    for action in actions:
        assert cast(str, action["owner"])
        assert cast(str, action["priority"]) in {"high", "medium", "low"}
        assert cast(str, action["status"]) in {"open", "in_progress", "closed"}
        assert cast(str, action["summary"])

        scenario_id = cast(str, action["scenario_id"])
        assert scenario_id in scenario_ids
        covered_scenarios.add(scenario_id)

        target_date = date.fromisoformat(cast(str, action["target_date"]))
        assert target_date >= execution_date

    assert covered_scenarios == scenario_ids


def test_st031_staging_report_summarizes_simulations_and_release_readiness() -> None:
    repo_root = _repo_root()
    report = (repo_root / "docs" / "runbooks" / "st-031-staging-alert-simulation-evidence.md").read_text(encoding="utf-8")

    assert "# ST-031 Staging Alert Simulation And Walkthrough Evidence" in report
    assert "docs/runbooks/st-031-staging-alert-simulation-evidence.sample.json" in report
    assert "parser_drift_spike" in report
    assert "missing_minutes_surge" in report
    assert "summarize_failure_spike" in report
    assert "stale_pipeline_dlq_backlog" in report
    assert "## Follow-Up Action Register" in report
    assert "ready_with_follow_up_actions" in report