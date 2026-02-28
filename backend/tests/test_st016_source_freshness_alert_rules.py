from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_ruleset() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-016-source-freshness-regression-alert-rules.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_baseline() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-016-alert-threshold-baseline.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_metric_injection_fixture() -> dict[str, Any]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st016_source_freshness_metric_injection.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_st016_task04_freshness_alert_rule_artifacts_exist() -> None:
    repo_root = _repo_root()

    assert (repo_root / "config" / "ops" / "st-016-source-freshness-regression-alert-rules.json").exists()
    assert (repo_root / "docs" / "runbooks" / "st-016-source-freshness-regression-alerting-runbook.md").exists()


def test_st016_task04_freshness_rules_align_with_baseline_thresholds_and_routing() -> None:
    baseline = _load_baseline()
    ruleset = _load_ruleset()

    baseline_class = next(
        item
        for item in cast(list[dict[str, Any]], baseline["alert_classes"])
        if item["alert_class"] == "source_freshness"
    )
    rules_by_severity = {
        rule["severity"]: rule for rule in cast(list[dict[str, Any]], ruleset["rules"])
    }

    for severity in ("warning", "critical"):
        rule = rules_by_severity[severity]
        baseline_threshold = baseline_class["thresholds"][severity]

        assert rule["threshold"]["value"] == baseline_threshold["value"]
        assert rule["threshold"]["for"] == baseline_threshold["for"]
        assert rule["threshold"]["evaluation_window"] == baseline_threshold["evaluation_window"]
        assert rule["owner_routing"] == baseline_class["ownership"]


def test_st016_task04_freshness_rule_payload_includes_triage_and_drift_correlation_fields() -> None:
    ruleset = _load_ruleset()

    required_fields = set(cast(list[str], ruleset["triage_metadata"]["required_fields"]))
    assert {
        "city_id",
        "source_id",
        "run_id",
        "last_success_at",
        "last_success_age_hours",
        "source_type",
        "source_url",
        "parser_drift_event_id",
    }.issubset(required_fields)

    correlation_fields = set(cast(list[str], ruleset["triage_metadata"]["correlation_fields"]))
    assert {"run_id", "source_id", "parser_drift_event_id"}.issubset(correlation_fields)


def test_st016_task04_controlled_metric_injection_triggers_expected_freshness_alerts() -> None:
    ruleset = _load_ruleset()
    fixture = _load_metric_injection_fixture()

    rules = cast(list[dict[str, Any]], ruleset["rules"])
    scenarios = cast(list[dict[str, Any]], fixture["scenarios"])

    for scenario in scenarios:
        observed = float(cast(float, scenario["observed_value"]))
        fired = {
            cast(str, rule["alert_id"])
            for rule in rules
            if observed >= float(cast(dict[str, Any], rule["threshold"])["value"])
        }

        expected = set(cast(list[str], scenario["expected_alert_ids"]))
        assert expected.issubset(fired)
