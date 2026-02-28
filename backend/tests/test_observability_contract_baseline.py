from __future__ import annotations

import json
from pathlib import Path


def _load_contract_fixture() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "backend" / "tests" / "fixtures" / "st011_observability_contract.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_st011_observability_contract_documents_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    contract_doc = repo_root / "docs" / "runbooks" / "st-011-observability-contract.md"
    checklist_doc = repo_root / "docs" / "runbooks" / "st-011-telemetry-naming-checklist.md"

    assert contract_doc.exists()
    assert checklist_doc.exists()

    content = contract_doc.read_text(encoding="utf-8")
    assert "## Required Structured Log Keys" in content
    assert "## Closed Label Sets" in content
    assert "## Baseline Metrics" in content
    assert "## Structured Log Examples" in content


def test_st011_structured_log_examples_lint_required_keys_and_closed_labels() -> None:
    contract = _load_contract_fixture()

    required_log_keys = set(contract["required_log_keys"])
    stages = set(contract["stages"])
    outcomes = set(contract["outcomes"])

    for event in contract["example_events"]:
        event_keys = set(event.keys())
        assert required_log_keys.issubset(event_keys)
        assert event["stage"] in stages
        assert event["outcome"] in outcomes


def test_st011_metric_names_are_unique_and_low_cardinality_labeled() -> None:
    contract = _load_contract_fixture()

    metrics = contract["metrics"]
    metric_names = [metric["name"] for metric in metrics]

    assert len(metric_names) == len(set(metric_names))
    assert all(name.startswith("councilsense_") for name in metric_names)

    forbidden_high_cardinality_labels = {
        "city_id",
        "meeting_id",
        "run_id",
        "dedupe_key",
        "user_id",
        "subscription_id",
    }

    for metric in metrics:
        labels = set(metric["labels"])
        assert labels == {"stage", "outcome"}
        assert labels.isdisjoint(forbidden_high_cardinality_labels)
