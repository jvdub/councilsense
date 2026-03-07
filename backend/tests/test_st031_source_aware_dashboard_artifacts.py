from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_dashboard() -> dict[str, object]:
    path = _repo_root() / "docs" / "runbooks" / "st-031-source-aware-dashboard.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_contract_fixture() -> dict[str, object]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st031_source_aware_observability_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_seed_telemetry() -> dict[str, object]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st031_source_aware_dashboard_seed_telemetry.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _as_panels(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [cast(dict[str, Any], panel) for panel in value]


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
        rejected = False
        for filter_name, filter_value in filters.items():
            if isinstance(filter_value, list) and labels.get(filter_name) not in filter_value:
                rejected = True
                break
        if not rejected:
            matched.append(sample)
    return matched


def test_st031_contract_document_and_dashboard_exist() -> None:
    repo_root = _repo_root()
    contract_doc = repo_root / "docs" / "runbooks" / "st-031-source-aware-observability-contract.md"
    dashboard_doc = repo_root / "docs" / "runbooks" / "st-031-source-aware-dashboard.json"

    assert contract_doc.exists()
    assert dashboard_doc.exists()

    content = contract_doc.read_text(encoding="utf-8")
    assert "## Stable Metrics" in content
    assert "## Cardinality Controls" in content
    assert "Alert routing and owner mappings are intentionally out of scope" in content


def test_st031_dashboard_panels_follow_on_call_triage_order() -> None:
    dashboard = _load_dashboard()
    panels = _as_panels(dashboard["panels"])

    assert dashboard["dashboard_id"] == "st-031-source-aware-ops"
    assert [panel["panel_id"] for panel in panels] == [
        "st031-source-stage-outcomes",
        "st031-source-coverage-ratio",
        "st031-citation-precision-ratio",
        "st031-pipeline-dlq-backlog-by-source",
        "st031-pipeline-dlq-oldest-age-by-source",
    ]


def test_st031_dashboard_metric_queries_match_contract_and_seeded_telemetry() -> None:
    dashboard = _load_dashboard()
    contract = _load_contract_fixture()
    seed = _load_seed_telemetry()

    contract_metrics = {metric["name"] for metric in cast(list[dict[str, object]], contract["metrics"])}
    metric_samples = cast(list[dict[str, object]], seed["metric_samples"])
    environment = cast(str, seed["environment"])

    for panel in _as_panels(dashboard["panels"]):
        query = cast(dict[str, Any], panel["query"])
        metric_name = str(query["metric"])
        assert metric_name in contract_metrics
        matched = _filter_metric_samples(
            metric_samples,
            metric_name=metric_name,
            environment=environment,
            filters=cast(dict[str, object], query["filters"]),
        )
        assert matched, f"panel {panel['panel_id']} produced no telemetry matches"


def test_st031_contract_only_allows_bounded_triage_labels() -> None:
    contract = _load_contract_fixture()
    forbidden_labels = {"meeting_id", "run_id", "artifact_id", "bundle_id", "dedupe_key", "error_message"}

    metrics = cast(list[dict[str, object]], contract["metrics"])
    for metric in metrics:
        labels = set(cast(list[str], metric["labels"]))
        assert labels.isdisjoint(forbidden_labels)

    stage_metric = next(metric for metric in metrics if metric["name"] == "councilsense_source_stage_outcomes_total")
    assert "source_id" not in cast(list[str], stage_metric["labels"])
