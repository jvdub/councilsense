from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_ruleset() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-016-ingestion-latency-notification-alert-rules.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_baseline() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-016-alert-threshold-baseline.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_metric_injection_fixture() -> dict[str, Any]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st016_alert_rule_metric_injection.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _compute_rate(samples: list[dict[str, Any]], numerator_outcomes: set[str], denominator_outcomes: set[str]) -> float:
    numerator = 0.0
    denominator = 0.0

    for sample in samples:
        outcome = cast(str, sample["outcome"])
        value = float(sample["value"])

        if outcome in numerator_outcomes:
            numerator += value
        if outcome in denominator_outcomes:
            denominator += value

    if denominator == 0:
        return 0.0
    return numerator / denominator


def _simulate_rule_fires_for_scenario(
    *,
    rules: list[dict[str, Any]],
    scenario: dict[str, Any],
) -> list[str]:
    class_rules = [rule for rule in rules if rule["alert_class"] == scenario["alert_class"]]
    fired: list[str] = []

    for rule in class_rules:
        threshold_value = float(cast(dict[str, Any], rule["threshold"])["value"])
        observed_value: float

        if rule["signal"] in {"failure_rate", "error_rate"}:
            calc = cast(dict[str, Any], rule["calculation"])
            observed_value = _compute_rate(
                samples=cast(list[dict[str, Any]], scenario["samples"]),
                numerator_outcomes=set(cast(list[str], calc["numerator_outcomes"])),
                denominator_outcomes=set(cast(list[str], calc["denominator_outcomes"])),
            )
        else:
            observed_value = float(scenario["observed_value"])

        if observed_value >= threshold_value:
            fired.append(cast(str, rule["alert_id"]))

    return fired


def test_st016_task02_alert_rule_artifacts_exist() -> None:
    repo_root = _repo_root()

    assert (repo_root / "config" / "ops" / "st-016-ingestion-latency-notification-alert-rules.json").exists()
    assert (repo_root / "docs" / "runbooks" / "st-016-ingestion-latency-notification-alerting-runbook.md").exists()


def test_st016_task02_rules_align_with_baseline_thresholds_and_routing() -> None:
    baseline = _load_baseline()
    ruleset = _load_ruleset()

    baseline_classes = {
        item["alert_class"]: item
        for item in cast(list[dict[str, Any]], baseline["alert_classes"])
        if item["alert_class"] in {"ingestion_failures", "pipeline_latency", "notification_errors"}
    }

    rules_by_class_and_severity = {
        (rule["alert_class"], rule["severity"]): rule for rule in cast(list[dict[str, Any]], ruleset["rules"])
    }

    for alert_class, class_payload in baseline_classes.items():
        for severity in ("warning", "critical"):
            rule = rules_by_class_and_severity[(alert_class, severity)]
            baseline_threshold = class_payload["thresholds"][severity]

            assert rule["threshold"]["value"] == baseline_threshold["value"]
            assert rule["threshold"]["for"] == baseline_threshold["for"]
            assert rule["threshold"]["evaluation_window"] == baseline_threshold["evaluation_window"]

            assert rule["owner_routing"] == class_payload["ownership"]


def test_st016_task02_alert_payload_metadata_contract_is_complete() -> None:
    baseline = _load_baseline()
    ruleset = _load_ruleset()

    baseline_required_fields = set(
        cast(list[str], baseline["triage_metadata_requirements"]["required_structured_fields"])
    )
    configured_required_fields = set(cast(list[str], ruleset["triage_metadata"]["required_fields"]))

    assert baseline_required_fields == configured_required_fields
    assert set(cast(list[str], ruleset["triage_metadata"]["required_for_escalation"])) == {
        "city_id",
        "source_id",
        "run_id",
    }

    required_label_mappings = {"city_id", "source_id", "run_id", "meeting_id", "stage", "outcome", "environment"}
    assert required_label_mappings.issubset(set(cast(dict[str, str], ruleset["triage_metadata"]["field_mapping"])))


def test_st016_task02_controlled_metric_injection_triggers_all_required_alert_classes() -> None:
    ruleset = _load_ruleset()
    fixture = _load_metric_injection_fixture()

    rules = cast(list[dict[str, Any]], ruleset["rules"])
    scenarios = cast(list[dict[str, Any]], fixture["scenarios"])

    fired_by_class: dict[str, set[str]] = {}

    for scenario in scenarios:
        fired = _simulate_rule_fires_for_scenario(rules=rules, scenario=scenario)
        expected = set(cast(list[str], scenario["expected_alert_ids"]))

        assert expected.issubset(set(fired))
        fired_by_class.setdefault(cast(str, scenario["alert_class"]), set()).update(fired)

    assert {"ingestion_failures", "pipeline_latency", "notification_errors"}.issubset(set(fired_by_class))


def test_st016_task02_escalation_path_routes_to_expected_owners() -> None:
    ruleset = _load_ruleset()
    fixture = _load_metric_injection_fixture()

    rules = {rule["alert_id"]: rule for rule in cast(list[dict[str, Any]], ruleset["rules"])}
    scenario = cast(list[dict[str, Any]], fixture["scenarios"])[0]

    firing_rule = rules["ingestion-failure-rate-critical"]
    labels = cast(dict[str, str], scenario["labels"])
    now = datetime(2026, 2, 28, 12, 0, tzinfo=UTC).isoformat()

    payload = {
        "alert_id": firing_rule["alert_id"],
        "alert_class": firing_rule["alert_class"],
        "city_id": labels["city_id"],
        "source_id": labels["source_id"],
        "run_id": labels["run_id"],
        "meeting_id": labels["meeting_id"],
        "stage": labels["stage"],
        "outcome": labels["outcome"],
        "environment": labels["environment"],
        "observed_value": 0.15,
        "threshold_value": firing_rule["threshold"]["value"],
        "evaluation_window": firing_rule["threshold"]["evaluation_window"],
        "triggered_at_utc": now,
        "owner_routing": firing_rule["owner_routing"],
    }

    assert payload["owner_routing"]["primary_role"] == "ops-ingestion-oncall"
    assert payload["owner_routing"]["secondary_role"] == "backend-oncall"
    assert payload["owner_routing"]["escalate_to"] == "platform-owner"
    assert payload["owner_routing"]["escalation_sla"] == "PT30M"
