from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_baseline_payload() -> dict[str, Any]:
    path = _repo_root() / "config" / "ops" / "st-016-alert-threshold-baseline.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_st016_baseline_artifacts_exist() -> None:
    repo_root = _repo_root()

    baseline_path = repo_root / "config" / "ops" / "st-016-alert-threshold-baseline.json"
    matrix_path = repo_root / "docs" / "runbooks" / "st-016-alert-threshold-and-ownership-baseline.md"
    backtest_path = repo_root / "docs" / "runbooks" / "st-016-alert-threshold-backtest-summary.md"

    assert baseline_path.exists()
    assert matrix_path.exists()
    assert backtest_path.exists()


def test_st016_threshold_matrix_covers_required_alert_classes_and_ownership() -> None:
    payload = _load_baseline_payload()

    assert payload["baseline_version"] == "st-016-alert-threshold-baseline-v1"
    assert payload["story_task"] == "TASK-ST-016-01"

    alert_classes = cast(list[dict[str, Any]], payload["alert_classes"])
    classes_by_name = {item["alert_class"]: item for item in alert_classes}

    assert set(classes_by_name) == {
        "ingestion_failures",
        "pipeline_latency",
        "notification_errors",
        "source_freshness",
    }

    for class_name, class_payload in classes_by_name.items():
        thresholds = cast(dict[str, dict[str, Any]], class_payload["thresholds"])
        ownership = cast(dict[str, str], class_payload["ownership"])

        assert "warning" in thresholds
        assert "critical" in thresholds
        assert thresholds["warning"]["value"] < thresholds["critical"]["value"]
        assert thresholds["warning"]["for"].startswith("PT")
        assert thresholds["critical"]["for"].startswith("PT")

        assert ownership["primary_role"]
        assert ownership["secondary_role"]
        assert ownership["escalate_to"]
        assert ownership["escalation_sla"].startswith("PT")

        assert class_payload["severity_mapping"]["warning"] == "warning"
        assert class_payload["severity_mapping"]["critical"] == "critical"
        assert class_payload["false_positive_tolerance"]
        assert class_payload["rationale"]

        if class_name in {"ingestion_failures", "notification_errors"}:
            assert class_payload["thresholds"]["warning"]["unit"] == "ratio"


def test_st016_triage_metadata_and_operational_unknowns_are_explicit() -> None:
    payload = _load_baseline_payload()

    triage = cast(dict[str, Any], payload["triage_metadata_requirements"])
    required_fields = set(cast(list[str], triage["required_structured_fields"]))

    assert {"city_id", "source_id", "run_id"}.issubset(required_fields)
    assert "required_context_note" in triage

    unknowns = cast(list[dict[str, str]], payload["operational_unknowns"])
    assert len(unknowns) >= 3

    for item in unknowns:
        assert item["unknown_id"].startswith("st016-unknown-")
        assert item["owner_role"]
        assert item["due_date"].startswith("2026-")
        assert item["status"] == "open"


def test_st016_docs_include_threshold_matrix_escalation_mapping_and_backtest_summary() -> None:
    repo_root = _repo_root()

    matrix_path = repo_root / "docs" / "runbooks" / "st-016-alert-threshold-and-ownership-baseline.md"
    matrix_content = matrix_path.read_text(encoding="utf-8")

    assert "## Threshold Matrix" in matrix_content
    assert "## Severity and Ownership Routing" in matrix_content
    assert "## Required Triage Metadata" in matrix_content
    assert "## Operational Unknowns (Tracked)" in matrix_content
    assert "config/ops/st-016-alert-threshold-baseline.json" in matrix_content

    backtest_path = repo_root / "docs" / "runbooks" / "st-016-alert-threshold-backtest-summary.md"
    backtest_content = backtest_path.read_text(encoding="utf-8")

    assert "## Results by Alert Class" in backtest_content
    assert "## Recommended Adjustments (Post-Launch Review)" in backtest_content
    assert "## Approval Record" in backtest_content
