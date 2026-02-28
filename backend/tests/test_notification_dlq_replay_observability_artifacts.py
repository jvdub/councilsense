from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_seed_telemetry() -> dict[str, object]:
    telemetry_path = _repo_root() / "backend" / "tests" / "fixtures" / "st011_dashboard_seed_telemetry.json"
    return json.loads(telemetry_path.read_text(encoding="utf-8"))


def test_st014_replay_observability_artifacts_exist() -> None:
    runbook_dir = _repo_root() / "docs" / "runbooks"

    assert (runbook_dir / "st-014-dlq-replay-alert-rules.json").exists()
    assert (runbook_dir / "st-014-dlq-replay-observability-runbook.md").exists()
    assert (runbook_dir / "st-014-dlq-replay-audit-evidence.md").exists()


def test_st014_backlog_growth_warning_rule_is_documented_and_active() -> None:
    alert_path = _repo_root() / "docs" / "runbooks" / "st-014-dlq-replay-alert-rules.json"
    payload = cast(dict[str, Any], json.loads(alert_path.read_text(encoding="utf-8")))

    rules = cast(list[dict[str, Any]], payload["rules"])
    backlog_warning = next(rule for rule in rules if rule["alert_id"] == "notification-dlq-backlog-growth-warning")

    assert backlog_warning["severity"] == "warning"
    assert backlog_warning["metric"] == "councilsense_notifications_dlq_backlog_count"
    assert backlog_warning["threshold"]["value"] == 5
    assert backlog_warning["threshold"]["for"] == "PT15M"
    assert backlog_warning["filters"]["stage"] == "notify_dlq"
    assert backlog_warning["filters"]["outcome"] == "backlog"


def test_st014_alert_simulation_detects_backlog_threshold_breach_from_seeded_telemetry() -> None:
    seed = _load_seed_telemetry()
    samples = cast(list[dict[str, object]], seed["metric_samples"])

    backlog_values = [
        float(value)
        for sample in samples
        if sample.get("metric") == "councilsense_notifications_dlq_backlog_count"
        and isinstance(sample.get("labels"), dict)
        and cast(dict[str, str], sample["labels"]).get("stage") == "notify_dlq"
        and cast(dict[str, str], sample["labels"]).get("outcome") == "backlog"
        and isinstance((value := sample.get("value")), int | float)
    ]

    assert backlog_values
    assert max(backlog_values) >= 5.0


def test_st014_runbook_defines_replay_success_failure_and_duplicate_rates() -> None:
    runbook_path = _repo_root() / "docs" / "runbooks" / "st-014-dlq-replay-observability-runbook.md"
    content = runbook_path.read_text(encoding="utf-8")

    assert "Replay success rate" in content
    assert "Replay failure rate" in content
    assert "Duplicate replay rate" in content
    assert "notification-dlq-backlog-growth-warning" in content
    assert "docs/runbooks/st-014-dlq-replay-alert-rules.json" in content
    assert "city_id" in content and "source_id" in content and "channel" in content
