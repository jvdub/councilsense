from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_dashboard() -> dict[str, object]:
    dashboard_path = _repo_root() / "docs" / "runbooks" / "st-011-baseline-dashboards.json"
    return json.loads(dashboard_path.read_text(encoding="utf-8"))


def _load_seed_telemetry() -> dict[str, object]:
    telemetry_path = _repo_root() / "backend" / "tests" / "fixtures" / "st011_dashboard_seed_telemetry.json"
    return json.loads(telemetry_path.read_text(encoding="utf-8"))


def _load_observability_contract() -> dict[str, object]:
    contract_path = _repo_root() / "backend" / "tests" / "fixtures" / "st011_observability_contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def _as_panel_list(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [cast(dict[str, Any], panel) for panel in value]


def _as_metric_list(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [cast(dict[str, Any], metric) for metric in value]


def _filter_metric_samples(
    metric_samples: list[dict[str, object]],
    *,
    metric_name: str,
    environment: str,
    filters: dict[str, object],
) -> list[dict[str, object]]:
    matched: list[dict[str, object]] = []
    for sample in metric_samples:
        if sample.get("metric") != metric_name:
            continue

        labels = sample.get("labels")
        if not isinstance(labels, dict):
            continue
        if labels.get("environment") != environment:
            continue

        stage_filter = filters.get("stage")
        if isinstance(stage_filter, list) and labels.get("stage") not in stage_filter:
            continue

        outcome_filter = filters.get("outcome")
        if isinstance(outcome_filter, list) and labels.get("outcome") not in outcome_filter:
            continue

        matched.append(sample)
    return matched


def _filter_source_rows(
    source_rows: list[dict[str, object]],
    *,
    environment: str,
    filters: dict[str, object],
) -> list[dict[str, object]]:
    statuses = filters.get("health_status")
    freshness_hours_gte = filters.get("freshness_hours_gte")

    matched: list[dict[str, object]] = []
    for row in source_rows:
        if row.get("environment") != environment:
            continue

        row_status = row.get("health_status")
        row_age_hours = row.get("last_success_age_hours")

        flagged_by_status = isinstance(statuses, list) and row_status in statuses
        flagged_by_staleness = isinstance(freshness_hours_gte, int | float) and isinstance(row_age_hours, int | float) and row_age_hours >= freshness_hours_gte

        if flagged_by_status or flagged_by_staleness:
            matched.append(row)

    return matched


def test_st011_baseline_dashboard_exists_and_has_required_scope_panels() -> None:
    dashboard = _load_dashboard()

    assert dashboard["dashboard_id"] == "st-011-baseline-ops"
    assert dashboard["default_time_window"] == "PT6H"

    filters = cast(list[dict[str, Any]], dashboard["filters"])
    assert isinstance(filters, list)
    environment_filter = next(item for item in filters if item["name"] == "environment")
    assert environment_filter["default"] == "local"

    panels = _as_panel_list(dashboard["panels"])
    panel_ids = {panel["panel_id"] for panel in panels}
    assert panel_ids == {
        "pipeline-stage-outcomes",
        "pipeline-stage-duration-p95",
        "notification-enqueue-outcomes",
        "notification-delivery-outcomes",
        "notification-delivery-duration-p95",
        "source-freshness-and-failure-snapshot",
    }


def test_st011_baseline_dashboard_metric_queries_match_contract_and_seeded_telemetry() -> None:
    dashboard = _load_dashboard()
    seed = _load_seed_telemetry()
    contract = _load_observability_contract()

    contract_metrics = {metric["name"] for metric in _as_metric_list(contract["metrics"])}
    metric_samples = cast(list[dict[str, object]], seed["metric_samples"])
    environment = cast(str, seed["environment"])

    assert isinstance(metric_samples, list)
    assert isinstance(environment, str)

    for panel in _as_panel_list(dashboard["panels"]):
        query = panel["query"]
        if query["kind"] not in {"metric_count", "metric_histogram"}:
            continue

        metric_name = query["metric"]
        assert metric_name in contract_metrics

        matched = _filter_metric_samples(
            metric_samples,
            metric_name=metric_name,
            environment=environment,
            filters=query["filters"],
        )
        assert matched, f"panel {panel['panel_id']} produced no telemetry matches"


def test_st011_source_snapshot_panel_flags_failing_or_stale_sources_for_city_level_triage() -> None:
    dashboard = _load_dashboard()
    seed = _load_seed_telemetry()

    environment = cast(str, seed["environment"])
    source_rows = cast(list[dict[str, object]], seed["source_snapshot_rows"])

    snapshot_panel = next(
        panel
        for panel in _as_panel_list(dashboard["panels"])
        if panel["panel_id"] == "source-freshness-and-failure-snapshot"
    )
    query = snapshot_panel["query"]

    matched = _filter_source_rows(
        source_rows,
        environment=environment,
        filters=query["filters"],
    )

    assert matched
    assert all("city_id" in row and "source_id" in row for row in matched)
    assert any(row["health_status"] == "failing" for row in matched)


def test_st011_dashboard_evidence_artifact_exists() -> None:
    evidence_path = _repo_root() / "docs" / "runbooks" / "st-011-baseline-dashboards-evidence.md"
    assert evidence_path.exists()

    content = evidence_path.read_text(encoding="utf-8")
    assert "# ST-011 Baseline Dashboard Evidence" in content
    assert "pipeline-stage-outcomes" in content
    assert "notification-delivery-outcomes" in content
    assert "source-freshness-and-failure-snapshot" in content
