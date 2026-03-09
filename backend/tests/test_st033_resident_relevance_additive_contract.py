from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest


DETAIL_FIELDS_WITH_ST027_BLOCKS = {
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
    "planned",
    "outcomes",
    "planned_outcome_mismatches",
}
ITEM_RELEVANCE_FIELDS = {"subject", "location", "action", "scale", "impact_tags"}
RELEVANCE_FIELD_KEYS = {"value", "confidence", "evidence_references_v2"}
IMPACT_TAG_KEYS = {"tag", "confidence", "evidence_references_v2"}
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
PRECISION_RANKS = {"offset": 0, "span": 1, "section": 2, "file": 3}
APPROVED_IMPACT_TAGS = ("housing", "traffic", "utilities", "parks", "fees", "land_use")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st033_resident_relevance_additive_contract_examples.json"


def _load_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path().read_text(encoding="utf-8")))


def _scenario(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], bundle["scenarios"])
    return next(scenario for scenario in scenarios if scenario["fixture_id"] == fixture_id)


def _matrix_entry(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    matrix = cast(list[dict[str, Any]], bundle["field_presence_matrix"])
    return next(entry for entry in matrix if entry["fixture_id"] == fixture_id)


def _strip_resident_relevance_fields(value: object) -> object:
    if isinstance(value, list):
        return [_strip_resident_relevance_fields(item) for item in value]

    if not isinstance(value, dict):
        return value

    return {
        key: _strip_resident_relevance_fields(item)
        for key, item in value.items()
        if key not in {"structured_relevance", *ITEM_RELEVANCE_FIELDS}
    }


def _normalize_excerpt(value: str) -> str:
    return " ".join(value.lower().split())


def _evidence_sort_key(evidence: dict[str, Any]) -> tuple[int, str, str, str, int, int, str, str]:
    return (
        PRECISION_RANKS[str(evidence["precision"])],
        str(evidence["document_kind"]).strip().lower(),
        str(evidence["artifact_id"]),
        str(evidence["section_path"]),
        evidence["char_start"] if evidence["char_start"] is not None else 10**9,
        evidence["char_end"] if evidence["char_end"] is not None else 10**9,
        _normalize_excerpt(str(evidence["excerpt"])),
        str(evidence["evidence_id"]),
    )


def _collect_field_paths(prefix: str, value: object) -> list[str]:
    if not isinstance(value, dict):
        return []

    paths = [prefix]
    evidence = value.get("evidence_references_v2")
    if isinstance(evidence, list):
        paths.append(f"{prefix}.evidence_references_v2")
    return paths


def _collect_tag_paths(prefix: str, value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    paths = [prefix]
    for index, tag in enumerate(value):
        if isinstance(tag, dict) and isinstance(tag.get("evidence_references_v2"), list):
            paths.append(f"{prefix}[{index}].evidence_references_v2")
    return paths


def _collect_present_resident_relevance_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    structured = payload.get("structured_relevance")
    if isinstance(structured, dict):
        paths.append("$.structured_relevance")
        for field_name in ("subject", "location", "action", "scale"):
            paths.extend(_collect_field_paths(f"$.structured_relevance.{field_name}", structured.get(field_name)))
        paths.extend(_collect_tag_paths("$.structured_relevance.impact_tags", structured.get("impact_tags")))

    for block_name in ("planned", "outcomes"):
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        items = block.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            prefix = f"$.{block_name}.items[{index}]"
            for field_name in ("subject", "location", "action", "scale"):
                paths.extend(_collect_field_paths(f"{prefix}.{field_name}", item.get(field_name)))
            paths.extend(_collect_tag_paths(f"{prefix}.impact_tags", item.get("impact_tags")))

    return paths


def _assert_evidence_list(evidence: list[dict[str, Any]]) -> None:
    assert all(set(item.keys()) == EVIDENCE_V2_KEYS for item in evidence)
    assert evidence == sorted(evidence, key=_evidence_sort_key)


def _assert_relevance_field(field: dict[str, Any]) -> None:
    assert set(field.keys()) <= RELEVANCE_FIELD_KEYS
    assert isinstance(field["value"], str)
    assert field["value"].strip()
    if "confidence" in field:
        assert field["confidence"] in {"high", "medium", "low"}
    if "evidence_references_v2" in field:
        evidence = cast(list[dict[str, Any]], field["evidence_references_v2"])
        _assert_evidence_list(evidence)


def _assert_impact_tags(tags: list[dict[str, Any]]) -> None:
    assert [tag["tag"] for tag in tags] == sorted(
        [tag["tag"] for tag in tags],
        key=lambda value: APPROVED_IMPACT_TAGS.index(value),
    )
    for tag in tags:
        assert set(tag.keys()) <= IMPACT_TAG_KEYS
        assert tag["tag"] in APPROVED_IMPACT_TAGS
        if "confidence" in tag:
            assert tag["confidence"] in {"high", "medium", "low"}
        if "evidence_references_v2" in tag:
            evidence = cast(list[dict[str, Any]], tag["evidence_references_v2"])
            _assert_evidence_list(evidence)


def _assert_payload_shapes(payload: dict[str, Any]) -> None:
    structured = payload.get("structured_relevance")
    if isinstance(structured, dict):
        for field_name in ("subject", "location", "action", "scale"):
            field = structured.get(field_name)
            if isinstance(field, dict):
                _assert_relevance_field(field)
        if isinstance(structured.get("impact_tags"), list):
            _assert_impact_tags(cast(list[dict[str, Any]], structured["impact_tags"]))

    for block_name in ("planned", "outcomes"):
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        items = block.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for field_name in ("subject", "location", "action", "scale"):
                field = item.get(field_name)
                if isinstance(field, dict):
                    _assert_relevance_field(field)
            if isinstance(item.get("impact_tags"), list):
                _assert_impact_tags(cast(list[dict[str, Any]], item["impact_tags"]))

    mismatch_block = payload.get("planned_outcome_mismatches")
    if isinstance(mismatch_block, dict) and isinstance(mismatch_block.get("items"), list):
        for item in cast(list[dict[str, Any]], mismatch_block["items"]):
            assert not (ITEM_RELEVANCE_FIELDS & set(item.keys()))


def test_st033_contract_fixture_bundle_covers_flag_and_legacy_states() -> None:
    bundle = _load_bundle()

    assert bundle["schema_version"] == "st033-resident-relevance-additive-contract-examples-v1"
    assert bundle["contract_version"] == "st-022-meeting-detail-v1"
    assert bundle["task_id"] == "TASK-ST-033-04"
    assert bundle["depends_on"] == ["TASK-ST-033-01", "TASK-ST-033-03"]
    assert bundle["projection_source"] == "publish_stage_metadata"
    assert bundle["sparse_data_expectations"] == [
        "Resident-relevance fields are omitted when unavailable; empty arrays are not used as placeholders for omitted resident-relevance values.",
        "Present sparse fields may omit evidence_references_v2 independently of other resident-relevance fields that still carry evidence.",
    ]

    scenarios = cast(list[dict[str, Any]], bundle["scenarios"])
    assert [scenario["fixture_id"] for scenario in scenarios] == [
        "st033-flag-off-baseline-with-st027-blocks",
        "st033-flag-on-full-structured-relevance",
        "st033-flag-on-sparse-structured-relevance",
        "st033-flag-on-legacy-structured-relevance-omitted",
    ]
    assert {scenario["flag_state"] for scenario in scenarios} == {"off", "on"}
    assert {scenario["structured_state"] for scenario in scenarios} == {
        "suppressed",
        "full",
        "sparse",
        "legacy_omitted",
    }


def test_st033_field_presence_matrix_matches_fixture_payload_shapes() -> None:
    bundle = _load_bundle()
    matrix = cast(list[dict[str, Any]], bundle["field_presence_matrix"])

    for entry in matrix:
        payload = cast(dict[str, Any], _scenario(bundle, str(entry["fixture_id"]))["payload"])
        present_fields = set(cast(list[str], entry["expected_present_top_level_fields"]))
        absent_fields = set(cast(list[str], entry["expected_absent_top_level_fields"]))
        present_paths = set(_collect_present_resident_relevance_paths(payload))

        assert present_fields <= set(payload.keys())
        assert not (absent_fields & set(payload.keys()))
        assert set(cast(list[str], entry["expected_present_resident_relevance_paths"])) <= present_paths
        assert not (
            set(cast(list[str], entry["expected_omitted_resident_relevance_paths"]))
            & present_paths
        )


def test_st033_flag_off_contract_preserves_st027_shape_without_resident_relevance() -> None:
    payload = cast(
        dict[str, Any],
        _scenario(_load_bundle(), "st033-flag-off-baseline-with-st027-blocks")["payload"],
    )

    assert DETAIL_FIELDS_WITH_ST027_BLOCKS == set(payload.keys())
    assert "structured_relevance" not in payload
    assert "subject" not in cast(dict[str, Any], payload["planned"])["items"][0]
    assert "action" not in cast(dict[str, Any], payload["outcomes"])["items"][0]


def test_st033_full_contract_uses_additive_evidence_v2_shapes_for_supported_fields() -> None:
    payload = cast(
        dict[str, Any],
        _scenario(_load_bundle(), "st033-flag-on-full-structured-relevance")["payload"],
    )

    _assert_payload_shapes(payload)

    structured = cast(dict[str, Any], payload["structured_relevance"])
    assert [tag["tag"] for tag in cast(list[dict[str, Any]], structured["impact_tags"])] == [
        "housing",
        "land_use",
    ]

    planned_item = cast(dict[str, Any], cast(dict[str, Any], payload["planned"])["items"][0])
    outcome_item = cast(dict[str, Any], cast(dict[str, Any], payload["outcomes"])["items"][0])
    mismatch_item = cast(dict[str, Any], cast(dict[str, Any], payload["planned_outcome_mismatches"])["items"][0])

    assert set(planned_item.keys()) & ITEM_RELEVANCE_FIELDS == {"subject", "location", "scale", "impact_tags"}
    assert set(outcome_item.keys()) & ITEM_RELEVANCE_FIELDS == {"subject", "location", "action", "scale", "impact_tags"}
    assert not (ITEM_RELEVANCE_FIELDS & set(mismatch_item.keys()))


def test_st033_sparse_contract_omits_unavailable_values_and_evidence_placeholders() -> None:
    scenario = _scenario(_load_bundle(), "st033-flag-on-sparse-structured-relevance")
    payload = cast(dict[str, Any], scenario["payload"])

    _assert_payload_shapes(payload)

    structured = cast(dict[str, Any], payload["structured_relevance"])
    assert "action" not in structured
    assert "scale" not in structured
    assert "evidence_references_v2" not in cast(dict[str, Any], structured["subject"])

    planned_item = cast(dict[str, Any], cast(dict[str, Any], payload["planned"])["items"][0])
    outcome_item = cast(dict[str, Any], cast(dict[str, Any], payload["outcomes"])["items"][0])

    assert set(planned_item.keys()) & ITEM_RELEVANCE_FIELDS == {"subject"}
    assert set(outcome_item.keys()) & ITEM_RELEVANCE_FIELDS == {"action", "impact_tags"}
    assert "evidence_references_v2" not in cast(list[dict[str, Any]], outcome_item["impact_tags"])[0]


def test_st033_legacy_contract_omits_resident_relevance_without_null_placeholders() -> None:
    payload = cast(
        dict[str, Any],
        _scenario(_load_bundle(), "st033-flag-on-legacy-structured-relevance-omitted")["payload"],
    )

    assert "structured_relevance" not in payload
    assert "subject" not in cast(dict[str, Any], payload["planned"])["items"][0]
    assert "impact_tags" not in cast(dict[str, Any], payload["outcomes"])["items"][0]
    assert all(item_value is not None for item_value in payload.values())


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st033-flag-off-baseline-with-st027-blocks",
        "st033-flag-on-full-structured-relevance",
        "st033-flag-on-sparse-structured-relevance",
        "st033-flag-on-legacy-structured-relevance-omitted",
    ],
)
def test_st033_legacy_consumers_can_ignore_resident_relevance_fields_without_shape_regressions(
    fixture_id: str,
) -> None:
    payload = cast(dict[str, Any], _scenario(_load_bundle(), fixture_id)["payload"])
    legacy_projection = cast(dict[str, Any], _strip_resident_relevance_fields(payload))

    assert set(legacy_projection.keys()) == DETAIL_FIELDS_WITH_ST027_BLOCKS
    assert "structured_relevance" not in legacy_projection

    for item in cast(list[dict[str, Any]], cast(dict[str, Any], legacy_projection["planned"])["items"]):
        assert not (ITEM_RELEVANCE_FIELDS & set(item.keys()))
        assert {"planned_id", "title"} <= set(item.keys())

    for item in cast(list[dict[str, Any]], cast(dict[str, Any], legacy_projection["outcomes"])["items"]):
        assert not (ITEM_RELEVANCE_FIELDS & set(item.keys()))
        assert {"outcome_id", "title"} <= set(item.keys())

    mismatch_items = cast(
        list[dict[str, Any]],
        cast(dict[str, Any], legacy_projection["planned_outcome_mismatches"])["items"],
    )
    assert all(not (ITEM_RELEVANCE_FIELDS & set(item.keys())) for item in mismatch_items)