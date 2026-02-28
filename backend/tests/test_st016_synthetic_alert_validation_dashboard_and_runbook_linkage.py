from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from statistics import median
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_ingestion_latency_notification_ruleset() -> dict[str, Any]:
    return _load_json(
        _repo_root() / "config" / "ops" / "st-016-ingestion-latency-notification-alert-rules.json"
    )


def _load_source_freshness_ruleset() -> dict[str, Any]:
    return _load_json(
        _repo_root() / "config" / "ops" / "st-016-source-freshness-regression-alert-rules.json"
    )


def _load_dashboard() -> dict[str, Any]:
    return _load_json(_repo_root() / "docs" / "runbooks" / "st-016-synthetic-alert-validation-dashboard.json")


def _load_synthetic_fixture() -> dict[str, Any]:
    return _load_json(_repo_root() / "backend" / "tests" / "fixtures" / "st016_synthetic_alert_validation_suite.json")


def _load_validation_report() -> str:
    path = _repo_root() / "docs" / "runbooks" / "st-016-synthetic-alert-validation-report.md"
    return path.read_text(encoding="utf-8")


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_st016_task05_artifacts_exist() -> None:
    repo_root = _repo_root()

    assert (repo_root / "backend" / "tests" / "fixtures" / "st016_synthetic_alert_validation_suite.json").exists()
    assert (repo_root / "docs" / "runbooks" / "st-016-synthetic-alert-validation-dashboard.json").exists()
    assert (repo_root / "docs" / "runbooks" / "st-016-parser-drift-monitoring-runbook.md").exists()
    assert (repo_root / "docs" / "runbooks" / "st-016-synthetic-alert-validation-report.md").exists()


def test_st016_task05_synthetic_suite_triggers_all_configured_alert_ids_and_signal_classes() -> None:
    ingestion_ruleset = _load_ingestion_latency_notification_ruleset()
    freshness_ruleset = _load_source_freshness_ruleset()
    fixture = _load_synthetic_fixture()

    configured_alert_ids = {
        cast(str, rule["alert_id"])
        for rule in [
            *cast(list[dict[str, Any]], ingestion_ruleset["rules"]),
            *cast(list[dict[str, Any]], freshness_ruleset["rules"]),
        ]
    }

    synthetic_results = cast(list[dict[str, Any]], fixture["synthetic_results"])
    synthetic_alert_ids = {
        cast(str, result["alert_id"])
        for result in synthetic_results
        if result["signal_type"] == "alert_rule"
    }

    assert configured_alert_ids.issubset(synthetic_alert_ids)

    signal_classes = {cast(str, result["signal_class"]) for result in synthetic_results}
    assert {
        "ingestion_failures",
        "pipeline_latency",
        "notification_errors",
        "source_freshness",
        "parser_drift",
    }.issubset(signal_classes)

    assert all(bool(result["triggered"]) for result in synthetic_results)


def test_st016_task05_runbook_and_owner_linkage_is_complete_for_all_alert_rules() -> None:
    repo_root = _repo_root()
    ingestion_ruleset = _load_ingestion_latency_notification_ruleset()
    freshness_ruleset = _load_source_freshness_ruleset()

    rules = [
        *cast(list[dict[str, Any]], ingestion_ruleset["rules"]),
        *cast(list[dict[str, Any]], freshness_ruleset["rules"]),
    ]

    owner_required_keys = {"primary_role", "secondary_role", "escalate_to", "escalation_sla"}
    covered_classes: set[str] = set()

    for rule in rules:
        runbook = cast(str, rule["runbook"]) if isinstance(rule.get("runbook"), str) else ""
        owner_routing = cast(dict[str, Any], rule["owner_routing"])

        assert runbook.strip(), f"missing runbook link for {rule['alert_id']}"
        assert owner_required_keys.issubset(set(owner_routing.keys()))
        assert (repo_root / runbook).exists(), f"runbook path does not exist for {rule['alert_id']}: {runbook}"

        covered_classes.add(cast(str, rule["alert_class"]))

    assert covered_classes == {
        "ingestion_failures",
        "pipeline_latency",
        "notification_errors",
        "source_freshness",
    }


def test_st016_task05_dashboard_has_required_visibility_panels_and_owner_context() -> None:
    repo_root = _repo_root()
    dashboard = _load_dashboard()

    assert dashboard["dashboard_id"] == "st-016-alert-hardening-validation"
    assert dashboard["default_time_window"] == "P7D"

    panels = cast(list[dict[str, Any]], dashboard["panels"])
    panel_map = {cast(str, panel["panel_id"]): panel for panel in panels}

    assert {
        "st016-alert-volume-by-class-and-severity",
        "st016-parser-drift-events-weekly",
        "st016-source-freshness-breaches-weekly",
        "st016-synthetic-trigger-success-and-latency",
        "st016-owner-context-and-runbook-linkage",
    }.issubset(set(panel_map))

    parser_drift_sql = cast(str, cast(dict[str, Any], panel_map["st016-parser-drift-events-weekly"]["query"])["sql"])
    freshness_sql = cast(
        str,
        cast(dict[str, Any], panel_map["st016-source-freshness-breaches-weekly"]["query"])["sql"],
    )
    assert "parser_drift_events" in parser_drift_sql
    assert "source_freshness_breach_events" in freshness_sql

    owner_rows = cast(
        list[dict[str, str]],
        cast(dict[str, Any], panel_map["st016-owner-context-and-runbook-linkage"]["query"])["rows"],
    )
    signal_classes = {row["signal_class"] for row in owner_rows}
    assert {
        "ingestion_failures",
        "pipeline_latency",
        "notification_errors",
        "source_freshness",
        "parser_drift",
    }.issubset(signal_classes)

    for row in owner_rows:
        runbook_path = row["runbook_path"]
        assert (repo_root / runbook_path).exists()
        assert row["primary_owner_role"]


def test_st016_task05_reported_metrics_match_synthetic_timings_and_counts() -> None:
    fixture = _load_synthetic_fixture()
    report_content = _load_validation_report()

    synthetic_results = cast(list[dict[str, Any]], fixture["synthetic_results"])
    reported_metrics = cast(dict[str, Any], fixture["reported_metrics"])

    triggered_count = sum(1 for result in synthetic_results if bool(result["triggered"]))
    success_rate = triggered_count / len(synthetic_results)

    detection_latencies_seconds = [
        (_parse_iso8601(cast(str, result["detected_at_utc"])) - _parse_iso8601(cast(str, result["injected_at_utc"]))).total_seconds()
        for result in synthetic_results
    ]

    parser_drift_events_per_week = sum(
        1
        for result in synthetic_results
        if result["signal_type"] == "drift_event" and result["signal_class"] == "parser_drift"
    )
    freshness_breach_count_per_week = sum(
        1
        for result in synthetic_results
        if result["signal_type"] == "alert_rule" and result["signal_class"] == "source_freshness"
    )

    assert reported_metrics["alert_trigger_success_rate"] == success_rate
    assert reported_metrics["median_detection_latency_seconds"] == median(detection_latencies_seconds)
    assert reported_metrics["parser_drift_events_per_week"] == parser_drift_events_per_week
    assert reported_metrics["freshness_breach_count_per_week"] == freshness_breach_count_per_week

    assert "alert_trigger_success_rate" in report_content
    assert "median_detection_latency_seconds" in report_content
    assert "parser_drift_events_per_week" in report_content
    assert "freshness_breach_count_per_week" in report_content
