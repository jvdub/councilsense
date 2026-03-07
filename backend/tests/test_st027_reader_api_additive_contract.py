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


def _matrix_entry(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    matrix = cast(list[dict[str, Any]], bundle["field_presence_matrix"])
    return next(entry for entry in matrix if entry["fixture_id"] == fixture_id)


def _present_item_level_evidence_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for block_name in ("planned", "outcomes", "planned_outcome_mismatches"):
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        items = block.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict) and "evidence_references_v2" in item:
                paths.append(f"$.{block_name}.items[{index}].evidence_references_v2")
    return paths


def _omitted_item_level_evidence_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for block_name in ("planned", "outcomes", "planned_outcome_mismatches"):
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        items = block.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict) and "evidence_references_v2" not in item:
                paths.append(f"$.{block_name}.items[{index}].evidence_references_v2")
    return paths


def test_st027_contract_fixture_bundle_covers_flag_off_and_flag_on_states() -> None:
    bundle = _load_bundle()

    assert bundle["schema_version"] == "st027-reader-api-additive-contract-examples-v1"
    assert bundle["contract_version"] == "st-022-meeting-detail-v1"
    assert bundle["task_id"] == "TASK-ST-027-01"
    assert bundle["matrix_task_id"] == "TASK-ST-027-04"
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


def test_st027_field_presence_matrix_matches_fixture_payload_shapes() -> None:
    bundle = _load_bundle()

    matrix = cast(list[dict[str, Any]], bundle["field_presence_matrix"])
    assert [entry["fixture_id"] for entry in matrix] == [
        "st027-flag-off-baseline",
        "st027-flag-on-evidence-v2-available",
        "st027-flag-on-evidence-v2-unavailable",
    ]

    for entry in matrix:
        payload = cast(dict[str, Any], _scenario(bundle, str(entry["fixture_id"]))["payload"])
        present_fields = set(cast(list[str], entry["expected_present_top_level_fields"]))
        absent_fields = set(cast(list[str], entry["expected_absent_top_level_fields"]))

        assert present_fields <= set(payload.keys())
        assert not (absent_fields & set(payload.keys()))
        assert _present_item_level_evidence_paths(payload) == cast(
            list[str],
            entry["expected_present_item_level_evidence_paths"],
        )
        assert _omitted_item_level_evidence_paths(payload) == cast(
            list[str],
            entry["expected_omitted_item_level_evidence_paths"],
        )


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

    mismatch_evidence = cast(list[dict[str, Any]], mismatch_items[0]["evidence_references_v2"])
    assert mismatch_evidence == [
        {
            "evidence_id": "ev2-st027-mismatch-100",
            "document_id": "doc-minutes-100",
            "document_kind": "minutes",
            "artifact_id": "artifact-minutes-100",
            "section_path": "minutes.section.8.vote",
            "page_start": 7,
            "page_end": 7,
            "char_start": 141,
            "char_end": 224,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Council deferred the procurement contract pending revised terms.",
        }
    ]


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
