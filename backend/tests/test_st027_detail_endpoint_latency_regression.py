from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from councilsense.app.st027_detail_latency import (
    DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION,
    DetailEndpointLatencyThresholds,
    build_benchmark_fixture_profile,
    build_detail_endpoint_latency_report,
    compute_percentile_ms,
    run_detail_endpoint_latency_benchmark,
    summarize_latency_samples,
)


def test_st027_latency_percentile_and_summary_are_deterministic() -> None:
    samples = [4.2, 5.0, 5.4, 6.1, 7.8]

    assert compute_percentile_ms(samples, percentile=95) == 7.8
    assert summarize_latency_samples(samples) == {
        "sample_count": 5,
        "min_ms": 4.2,
        "mean_ms": 5.7,
        "median_ms": 5.4,
        "p95_ms": 7.8,
        "p99_ms": 7.8,
        "max_ms": 7.8,
    }


def test_st027_latency_report_evaluates_budget_and_stability() -> None:
    report = build_detail_endpoint_latency_report(
        flag_off_runs_ms=[[9.5, 10.0, 10.4], [9.8, 10.1, 10.6], [9.7, 10.2, 10.3]],
        flag_on_runs_ms=[[12.6, 13.0, 13.4], [12.8, 13.1, 13.5], [12.9, 13.2, 13.6]],
        repeat_count=3,
        sample_count=3,
        warmup_count=1,
        thresholds=DetailEndpointLatencyThresholds(
            flag_off_p95_max_ms=20.0,
            flag_on_p95_max_ms=25.0,
            flag_on_p95_delta_max_ms=5.0,
            flag_on_p95_ratio_max=1.4,
            repeat_run_p95_spread_max_ms=1.5,
        ),
        fixture_profile=build_benchmark_fixture_profile(),
        captured_by="test-suite",
        environment="unit-test",
        generated_at_utc=datetime(2026, 3, 7, 18, 0, 0, tzinfo=UTC),
    )

    assert report["schema_version"] == DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION
    assert report["measurement"]["repeat_count"] == 3
    assert report["regression_check"] == {
        "flag_off_p95_ms": 10.6,
        "flag_on_p95_ms": 13.6,
        "flag_on_p95_delta_ms": 3.0,
        "flag_on_p95_ratio": 1.283,
        "within_budget": True,
        "failed_checks": [],
        "rollback_recommended": False,
    }

    scenarios = {scenario["scenario_id"]: scenario for scenario in report["scenarios"]}
    assert scenarios["flag_off_baseline"]["stability"] == {
        "repeat_count": 3,
        "p95_spread_ms": 0.3,
        "within_budget": True,
    }
    assert scenarios["flag_on_additive"]["aggregate_summary"]["p95_ms"] == 13.6


def test_st027_latency_benchmark_harness_runs_for_flag_off_and_flag_on() -> None:
    report = run_detail_endpoint_latency_benchmark(
        repeat_count=2,
        sample_count=5,
        warmup_count=2,
        captured_by="test-harness",
        environment="pytest",
        generated_at_utc=datetime(2026, 3, 7, 18, 30, 0, tzinfo=UTC),
    )

    assert report["schema_version"] == DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION
    assert report["measurement"]["repeat_count"] == 2
    assert report["measurement"]["sample_count_per_repeat"] == 5
    assert len(report["scenarios"]) == 2
    assert {scenario["scenario_id"] for scenario in report["scenarios"]} == {
        "flag_off_baseline",
        "flag_on_additive",
    }
    for scenario in report["scenarios"]:
        assert scenario["aggregate_summary"]["sample_count"] == 10
        assert scenario["aggregate_summary"]["p95_ms"] >= 0.0
        assert scenario["stability"]["repeat_count"] == 2


def test_st027_latency_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "config" / "ops" / "st-027-detail-endpoint-latency-report.json"
    runbook_path = repo_root / "docs" / "runbooks" / "st-027-detail-endpoint-latency-readiness.md"

    assert report_path.exists()
    assert runbook_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    content = runbook_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION
    assert payload["task_id"] == "TASK-ST-027-05"
    assert payload["measurement"]["repeat_count"] == 3
    assert payload["measurement"]["sample_count_per_repeat"] == 75
    assert payload["regression_check"]["within_budget"] is True
    assert {scenario["scenario_id"] for scenario in payload["scenarios"]} == {
        "flag_off_baseline",
        "flag_on_additive",
    }
    assert "flag_off_p95_max_ms" in payload["thresholds"]
    assert "flag_on_p95_delta_max_ms" in payload["thresholds"]

    assert "## Measurement Procedure" in content
    assert "## Acceptance Thresholds" in content
    assert "## Mitigation and Rollback" in content
    assert "ST022_API_ADDITIVE_V1_FIELDS_ENABLED=false" in content