from __future__ import annotations

import json
from pathlib import Path

from councilsense.app.st027_detail_latency import DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION


def test_st033_latency_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "config" / "ops" / "st-033-detail-endpoint-latency-report.json"
    runbook_path = repo_root / "docs" / "runbooks" / "st-033-detail-endpoint-latency-readiness.md"

    assert report_path.exists()
    assert runbook_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    content = runbook_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION
    assert payload["task_id"] == "TASK-ST-033-05"
    assert payload["story_id"] == "ST-033"
    assert payload["measurement"]["repeat_count"] == 3
    assert payload["measurement"]["sample_count_per_repeat"] == 75
    assert payload["measurement"]["warmup_count_per_repeat"] == 15
    assert payload["regression_check"]["within_budget"] is True
    assert {scenario["scenario_id"] for scenario in payload["scenarios"]} == {
        "flag_off_baseline",
        "flag_on_resident_relevance_additive",
    }
    assert payload["measurement"]["fixture_profile"]["fixture_id"] == "st033-flag-on-full-structured-relevance"
    assert payload["measurement"]["fixture_profile"]["top_level_impact_tag_count"] == 2
    assert payload["measurement"]["fixture_profile"]["planned_item_count"] == 1
    assert payload["measurement"]["fixture_profile"]["outcome_item_count"] == 1

    assert "## Measurement Procedure" in content
    assert "## Acceptance Thresholds" in content
    assert "## Mitigation and Rollback" in content
    assert "ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED=false" in content