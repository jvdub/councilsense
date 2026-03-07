from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
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


def _parse_duration(duration: str) -> timedelta:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    assert match is not None, f"unsupported duration {duration}"
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _resolve_threshold(rule: dict[str, Any], environment: str) -> dict[str, Any]:
    threshold = dict(cast(dict[str, Any], rule["threshold"]))
    overrides = cast(dict[str, Any], threshold.get("environment_overrides") or {})
    override = cast(dict[str, Any], overrides.get(environment) or {})
    threshold.update(override)
    return threshold


def _compute_failure_rate(samples: list[dict[str, Any]], rule: dict[str, Any]) -> float:
    calculation = cast(dict[str, Any], cast(dict[str, Any], rule["signal_source"])["calculation"])
    numerator_outcomes = set(cast(list[str], calculation["numerator_outcomes"]))
    denominator_outcomes = set(cast(list[str], calculation["denominator_outcomes"]))

    numerator = 0.0
    denominator = 0.0
    for sample in samples:
        outcome = cast(str, sample["outcome"])
        value = float(sample["value"])
        if outcome in numerator_outcomes:
            numerator += value
        if outcome in denominator_outcomes:
            denominator += value

    minimum_denominator = int(calculation["minimum_denominator"])
    if denominator < minimum_denominator or denominator == 0.0:
        return 0.0
    return numerator / denominator


def _compute_observed_value(rule: dict[str, Any], scenario: dict[str, Any]) -> float:
    signal = cast(str, rule["signal"])
    if signal == "event_count":
        return float(scenario["observed_count"])
    if signal == "below_threshold_count":
        signal_source = cast(dict[str, Any], rule["signal_source"])
        comparison_value = float(signal_source["comparison_value"])
        return float(sum(1 for sample in cast(list[dict[str, Any]], scenario["samples"]) if float(sample["value"]) <= comparison_value))
    if signal == "failure_rate":
        return _compute_failure_rate(cast(list[dict[str, Any]], scenario["samples"]), rule)
    if signal == "age_with_backlog":
        metrics = cast(dict[str, Any], scenario["metrics"])
        return float(metrics["oldest_age_seconds"])
    raise AssertionError(f"unsupported signal {signal}")


def _gating_conditions_met(rule: dict[str, Any], scenario: dict[str, Any], environment: str) -> bool:
    if cast(str, rule["signal"]) != "age_with_backlog":
        return True

    threshold = _resolve_threshold(rule, environment)
    metrics = cast(dict[str, Any], scenario["metrics"])
    gating_conditions = cast(list[dict[str, Any]], threshold["gating_conditions"])
    for condition in gating_conditions:
        if condition["metric"] != "councilsense_pipeline_dlq_backlog_count":
            continue
        if float(metrics["backlog_count"]) < float(condition["value"]):
            return False
    return True


def _simulate_fired_alert_ids(rules: list[dict[str, Any]], scenario: dict[str, Any]) -> set[str]:
    environment = cast(str, scenario["environment"])
    fired: set[str] = set()
    for rule in rules:
        if rule["alert_class"] != scenario["alert_class"]:
            continue
        if not _gating_conditions_met(rule, scenario, environment):
            continue
        observed_value = _compute_observed_value(rule, scenario)
        threshold = _resolve_threshold(rule, environment)
        if observed_value >= float(threshold["value"]):
            fired.add(cast(str, rule["alert_id"]))
    return fired


def _dedupe_key(rule: dict[str, Any], payload: dict[str, Any]) -> tuple[str, ...]:
    fields = cast(list[str], cast(dict[str, Any], rule["noise_controls"])["dedupe_key_fields"])
    return tuple(str(payload.get(field, "")) for field in fields)


def test_st031_alert_policy_artifacts_exist() -> None:
    repo_root = _repo_root()
    assert (repo_root / "config" / "ops" / "st-031-source-aware-alert-rules.json").exists()
    assert (repo_root / "docs" / "runbooks" / "st-031-source-aware-alert-policy.md").exists()
    assert (repo_root / "docs" / "runbooks" / "st-031-source-aware-incident-response.md").exists()
    assert (repo_root / "docs" / "runbooks" / "st-031-runbook-walkthrough-checklist.md").exists()


def test_st031_alert_policy_covers_required_classes_routes_and_environment_overrides() -> None:
    ruleset = _load_ruleset()
    rules = cast(list[dict[str, Any]], ruleset["rules"])

    assert len(rules) == 8
    assert {
        cast(str, rule["alert_class"])
        for rule in rules
    } == {
        "parser_drift_spike",
        "missing_minutes_surge",
        "summarize_failure_spike",
        "stale_pipeline_dlq_backlog",
    }

    for alert_class in {
        "parser_drift_spike",
        "missing_minutes_surge",
        "summarize_failure_spike",
        "stale_pipeline_dlq_backlog",
    }:
        severities = {
            cast(str, rule["severity"])
            for rule in rules
            if rule["alert_class"] == alert_class
        }
        assert severities == {"warning", "critical"}

    parser_warning = next(rule for rule in rules if rule["alert_id"] == "st031-parser-drift-spike-warning")
    assert cast(dict[str, Any], parser_warning["threshold"])["environment_overrides"]["local"]["value"] == 1

    dlq_warning = next(rule for rule in rules if rule["alert_id"] == "st031-stale-pipeline-dlq-backlog-warning")
    local_override = cast(dict[str, Any], cast(dict[str, Any], dlq_warning["threshold"])["environment_overrides"])["local"]
    assert local_override["value"] == 1800
    assert cast(list[dict[str, Any]], local_override["gating_conditions"])[0]["value"] == 1


def test_st031_alert_payload_contracts_are_actionable_and_reference_existing_diagnostics() -> None:
    ruleset = _load_ruleset()
    fixture = _load_fixture()
    rules = {cast(str, rule["alert_class"]): cast(dict[str, Any], rule) for rule in cast(list[dict[str, Any]], ruleset["rules"]) if rule["severity"] == "warning"}

    common_fields = set(cast(list[str], cast(dict[str, Any], ruleset["triage_metadata"])["required_common_fields"]))
    required_for_escalation = set(cast(list[str], cast(dict[str, Any], ruleset["triage_metadata"])["required_for_escalation"]))
    assert required_for_escalation == {"city_id", "source_id", "run_id"}

    for scenario in cast(list[dict[str, Any]], fixture["scenarios"]):
        rule = rules[cast(str, scenario["alert_class"])]
        payload = cast(dict[str, Any], scenario["payload"])
        required_fields = common_fields | set(cast(list[str], rule["payload_context_fields"]))
        assert required_fields.issubset(set(payload.keys()))

        dashboard_path = _repo_root() / cast(str, payload["dashboard_path"])
        assert dashboard_path.exists()

        runbook_path = _repo_root() / cast(str, rule["runbook"])
        assert runbook_path.exists()
        assert cast(str, rule["remediation_action"])

        for path_value in cast(list[str], cast(dict[str, Any], rule["diagnostic_links"])["supporting_paths"]):
            assert (_repo_root() / path_value).exists()


def test_st031_each_alert_class_has_one_primary_runbook_and_remediation_mapping() -> None:
    ruleset = _load_ruleset()
    rules = cast(list[dict[str, Any]], ruleset["rules"])

    by_class: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        by_class.setdefault(cast(str, rule["alert_class"]), []).append(rule)

    for alert_class, class_rules in by_class.items():
        runbooks = {cast(str, rule["runbook"]) for rule in class_rules}
        remediation_actions = {cast(str, rule["remediation_action"]) for rule in class_rules}
        assert len(runbooks) == 1, alert_class
        assert len(remediation_actions) == 1, alert_class


def test_st031_primary_runbook_covers_triage_replay_confidence_and_rollback() -> None:
    repo_root = _repo_root()
    runbook_path = repo_root / "docs" / "runbooks" / "st-031-source-aware-incident-response.md"
    checklist_path = repo_root / "docs" / "runbooks" / "st-031-runbook-walkthrough-checklist.md"

    runbook = runbook_path.read_text(encoding="utf-8")
    checklist = checklist_path.read_text(encoding="utf-8")

    assert "## Owner Routing And Alert-to-Action Matrix" in runbook
    assert "## Replay Procedure" in runbook
    assert "## Confidence-Policy Decision Tree" in runbook
    assert "## Rollback Decision Tree" in runbook
    assert "parser_drift_spike" in runbook
    assert "missing_minutes_surge" in runbook
    assert "summarize_failure_spike" in runbook
    assert "stale_pipeline_dlq_backlog" in runbook
    assert "TASK-ST-031-05" in checklist
    assert "Each ST-031 alert class maps to one primary runbook entry point." in checklist


def test_st031_controlled_scenarios_trigger_expected_alert_ids_and_owner_routes() -> None:
    ruleset = _load_ruleset()
    fixture = _load_fixture()
    rules = cast(list[dict[str, Any]], ruleset["rules"])
    rules_by_id = {cast(str, rule["alert_id"]): cast(dict[str, Any], rule) for rule in rules}

    for scenario in cast(list[dict[str, Any]], fixture["scenarios"]):
        fired = _simulate_fired_alert_ids(rules, scenario)
        expected = set(cast(list[str], scenario["expected_alert_ids"]))
        assert expected.issubset(fired)

        for alert_id in expected:
            owner_routing = cast(dict[str, Any], rules_by_id[alert_id]["owner_routing"])
            assert {"primary_role", "secondary_role", "escalate_to", "escalation_sla"}.issubset(owner_routing)


def test_st031_dedupe_and_suppression_controls_reduce_repeat_noise() -> None:
    ruleset = _load_ruleset()
    fixture = _load_fixture()
    rules_by_id = {
        cast(str, rule["alert_id"]): cast(dict[str, Any], rule) for rule in cast(list[dict[str, Any]], ruleset["rules"])
    }

    for sequence in cast(list[dict[str, Any]], fixture["dedupe_sequences"]):
        rule = rules_by_id[cast(str, sequence["rule_id"])]
        noise_controls = cast(dict[str, Any], rule["noise_controls"])
        dedupe_window = _parse_duration(cast(str, noise_controls["dedupe_window"]))
        suppression_conditions = set(cast(list[str], noise_controls["suppression_conditions"]))
        seen: dict[tuple[str, ...], datetime] = {}

        for event in cast(list[dict[str, Any]], sequence["events"]):
            payload = cast(dict[str, Any], event["payload"])
            suppression_context = cast(dict[str, Any], event["suppression_context"])
            timestamp = datetime.fromisoformat(cast(str, event["triggered_at_utc"]))
            suppressed = any(bool(suppression_context.get(condition)) for condition in suppression_conditions)

            key = _dedupe_key(rule, payload)
            last_emitted_at = seen.get(key)
            if not suppressed and last_emitted_at is not None and timestamp - last_emitted_at < dedupe_window:
                suppressed = True

            assert suppressed is bool(event["expected_suppressed"])
            if not suppressed:
                seen[key] = timestamp