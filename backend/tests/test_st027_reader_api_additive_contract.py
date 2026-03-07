from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


BASELINE_DETAIL_FIELDS = {
    "id",
    "city_id",
    "meeting_uid",
    "title",
    "created_at",
    "updated_at",
    "status",
    "confidence_label",
    "reader_low_confidence",
    "publication_id",
    "published_at",
    "summary",
    "key_decisions",
    "key_actions",
    "notable_topics",
    "claims",
    "evidence_references",
    "evidence_references_v2",
}
ADDITIVE_BLOCK_FIELDS = {"planned", "outcomes", "planned_outcome_mismatches"}
EVIDENCE_V2_KEYS = {
    "evidence_id",
    "document_id",
    "document_kind",
    "artifact_id",
    "section_path",
    "page_start",
    "page_end",
    "char_start",
    "char_end",
    "precision",
    "confidence",
    "excerpt",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st027_reader_api_additive_contract_examples.json"


def _load_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path().read_text(encoding="utf-8")))


def _scenario(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], bundle["scenarios"])
    return next(scenario for scenario in scenarios if scenario["fixture_id"] == fixture_id)


def test_st027_contract_fixture_bundle_covers_flag_off_and_flag_on_states() -> None:
    bundle = _load_bundle()

    assert bundle["schema_version"] == "st027-reader-api-additive-contract-examples-v1"
    assert bundle["contract_version"] == "st-022-meeting-detail-v1"
    assert bundle["task_id"] == "TASK-ST-027-01"
    assert bundle["feature_flag"] == "st022_api_additive_v1_fields_enabled"

    scenarios = cast(list[dict[str, Any]], bundle["scenarios"])
    assert [scenario["fixture_id"] for scenario in scenarios] == [
        "st027-flag-off-baseline",
        "st027-flag-on-evidence-v2-available",
        "st027-flag-on-evidence-v2-unavailable",
    ]
    assert {scenario["flag_state"] for scenario in scenarios} == {"off", "on"}
    assert {scenario["evidence_v2_state"] for scenario in scenarios} == {
        "baseline_only",
        "available",
        "unavailable",
    }


def test_st027_flag_off_example_is_baseline_compatible() -> None:
    payload = cast(dict[str, Any], _scenario(_load_bundle(), "st027-flag-off-baseline")["payload"])

    assert set(payload.keys()) == BASELINE_DETAIL_FIELDS
    assert not (ADDITIVE_BLOCK_FIELDS & set(payload.keys()))
    assert isinstance(payload["evidence_references"], list)
    assert isinstance(payload["evidence_references_v2"], list)


def test_st027_flag_on_example_includes_additive_blocks_without_changing_baseline_fields() -> None:
    payload = cast(dict[str, Any], _scenario(_load_bundle(), "st027-flag-on-evidence-v2-available")["payload"])

    assert BASELINE_DETAIL_FIELDS <= set(payload.keys())
    assert ADDITIVE_BLOCK_FIELDS <= set(payload.keys())

    planned_items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["planned"])["items"])
    outcome_items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["outcomes"])["items"])
    mismatch_items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["planned_outcome_mismatches"])["items"])

    for item in [*planned_items, *outcome_items, *mismatch_items]:
        assert "evidence_references_v2" in item
        evidence = cast(list[dict[str, Any]], item["evidence_references_v2"])
        assert evidence == [] or all(set(reference.keys()) == EVIDENCE_V2_KEYS for reference in evidence)


def test_st027_flag_on_example_omits_item_level_evidence_v2_when_unavailable() -> None:
    scenario = _scenario(_load_bundle(), "st027-flag-on-evidence-v2-unavailable")
    payload = cast(dict[str, Any], scenario["payload"])
    omitted_paths = cast(list[str], scenario["omitted_field_paths"])

    assert BASELINE_DETAIL_FIELDS <= set(payload.keys())
    assert ADDITIVE_BLOCK_FIELDS <= set(payload.keys())

    planned_item = cast(dict[str, Any], cast(dict[str, Any], payload["planned"])["items"][0])
    outcome_item = cast(dict[str, Any], cast(dict[str, Any], payload["outcomes"])["items"][0])
    mismatch_item = cast(dict[str, Any], cast(dict[str, Any], payload["planned_outcome_mismatches"])["items"][0])

    assert omitted_paths == [
        "$.planned.items[0].evidence_references_v2",
        "$.outcomes.items[0].evidence_references_v2",
        "$.planned_outcome_mismatches.items[0].evidence_references_v2",
    ]
    assert "evidence_references_v2" not in planned_item
    assert "evidence_references_v2" not in outcome_item
    assert "evidence_references_v2" not in mismatch_item
    assert planned_item.get("evidence_references_v2") is None
    assert outcome_item.get("evidence_references_v2") is None
    assert mismatch_item.get("evidence_references_v2") is None
