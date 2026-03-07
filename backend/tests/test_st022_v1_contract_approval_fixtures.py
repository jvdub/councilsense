from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st022_v1_contract_approval_fixtures.json"


def _snapshot_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st026_evidence_v2_publication_snapshot.json"


def _load_fixture_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path().read_text(encoding="utf-8")))


def _load_snapshot_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_snapshot_path().read_text(encoding="utf-8")))


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


def _build_evidence_snapshot(bundle: dict[str, Any]) -> dict[str, Any]:
    fixtures = cast(list[dict[str, Any]], bundle["fixtures"])
    return {
        "schema_version": "st026-evidence-v2-publication-snapshot-v1",
        "fixtures": [
            {
                "fixture_id": fixture["fixture_id"],
                "publication_status": fixture["publication_status"],
                "planned": [
                    {
                        "item_id": item["planned_id"],
                        "evidence_references_v2": item["evidence_references_v2"],
                    }
                    for item in cast(list[dict[str, Any]], cast(dict[str, Any], fixture["planned"])["items"])
                ],
                "outcomes": [
                    {
                        "item_id": item["outcome_id"],
                        "evidence_references_v2": item["evidence_references_v2"],
                    }
                    for item in cast(list[dict[str, Any]], cast(dict[str, Any], fixture["outcomes"])["items"])
                ],
                "planned_outcome_mismatches": [
                    {
                        "item_id": item["mismatch_id"],
                        "evidence_references_v2": item["evidence_references_v2"],
                    }
                    for item in cast(
                        list[dict[str, Any]],
                        cast(dict[str, Any], fixture["planned_outcome_mismatches"])["items"],
                    )
                ],
            }
            for fixture in fixtures
        ],
    }


def test_st022_fixture_bundle_has_approved_signoff_and_expected_scenarios() -> None:
    bundle = _load_fixture_bundle()

    assert bundle["schema_version"] == "st022-v1-contract-approval-fixtures-v1"
    assert bundle["contract_version"] == "st-022-meeting-detail-v1"

    approval = cast(dict[str, Any], bundle["approval"])
    assert approval["status"] == "approved"

    reviewers = cast(list[dict[str, Any]], approval["reviewers"])
    roles = {reviewer["role"] for reviewer in reviewers}
    assert roles == {"backend_owner", "frontend_owner", "product_platform_owner"}
    assert all(reviewer["status"] == "approved" for reviewer in reviewers)

    fixtures = cast(list[dict[str, Any]], bundle["fixtures"])
    scenarios = {fixture["scenario"] for fixture in fixtures}
    assert scenarios == {"nominal", "partial_source", "limited_confidence"}


def test_st022_fixtures_cover_required_v1_blocks_and_limited_confidence_case() -> None:
    fixtures = cast(list[dict[str, Any]], _load_fixture_bundle()["fixtures"])

    for fixture in fixtures:
        assert "planned" in fixture
        assert "outcomes" in fixture
        assert "planned_outcome_mismatches" in fixture

        planned = cast(dict[str, Any], fixture["planned"])
        outcomes = cast(dict[str, Any], fixture["outcomes"])
        mismatches = cast(dict[str, Any], fixture["planned_outcome_mismatches"])

        assert isinstance(planned["items"], list)
        assert isinstance(outcomes["items"], list)
        assert isinstance(mismatches["items"], list)

        for item in cast(list[dict[str, Any]], planned["items"]):
            assert "evidence_references_v2" in item

        for item in cast(list[dict[str, Any]], outcomes["items"]):
            assert "evidence_references_v2" in item

        for item in cast(list[dict[str, Any]], mismatches["items"]):
            assert "evidence_references_v2" in item

    limited = next(fixture for fixture in fixtures if fixture["scenario"] == "limited_confidence")
    assert limited["publication_status"] == "limited_confidence"


def test_st022_evidence_references_v2_have_source_kind_and_precision_metadata() -> None:
    fixtures = cast(list[dict[str, Any]], _load_fixture_bundle()["fixtures"])

    seen_document_kinds: set[str] = set()
    precision_values: set[str] = set()

    for fixture in fixtures:
        containers = [fixture["planned"]["items"], fixture["outcomes"]["items"], fixture["planned_outcome_mismatches"]["items"]]

        for items in containers:
            for item in cast(list[dict[str, Any]], items):
                for evidence in cast(list[dict[str, Any]], item["evidence_references_v2"]):
                    assert set(evidence.keys()) == EVIDENCE_V2_KEYS
                    seen_document_kinds.add(str(evidence["document_kind"]))
                    precision_values.add(str(evidence["precision"]))
                    assert evidence["confidence"] in {"high", "medium", "low"}
                    assert isinstance(evidence["section_path"], str)
                    assert isinstance(evidence["artifact_id"], str)
                    assert isinstance(evidence["excerpt"], str)
                    assert evidence["document_id"] is None or isinstance(evidence["document_id"], str)
                    assert evidence["page_start"] is None or isinstance(evidence["page_start"], int)
                    assert evidence["page_end"] is None or isinstance(evidence["page_end"], int)
                    assert evidence["char_start"] is None or isinstance(evidence["char_start"], int)
                    assert evidence["char_end"] is None or isinstance(evidence["char_end"], int)
                assert cast(list[dict[str, Any]], item["evidence_references_v2"]) == sorted(
                    cast(list[dict[str, Any]], item["evidence_references_v2"]),
                    key=_evidence_sort_key,
                )

    assert seen_document_kinds == {"minutes", "agenda", "packet"}
    assert precision_values == {"offset", "span", "section", "file"}


def test_st026_publication_fixture_bundle_covers_mixed_precision_and_multi_document_references() -> None:
    fixtures = cast(list[dict[str, Any]], _load_fixture_bundle()["fixtures"])
    nominal = next(fixture for fixture in fixtures if fixture["fixture_id"] == "st022-nominal-multi-source")

    planned_evidence = cast(list[dict[str, Any]], nominal["planned"]["items"][0]["evidence_references_v2"])
    outcome_evidence = cast(list[dict[str, Any]], nominal["outcomes"]["items"][0]["evidence_references_v2"])
    mismatch_evidence = cast(
        list[dict[str, Any]],
        nominal["planned_outcome_mismatches"]["items"][0]["evidence_references_v2"],
    )

    assert {evidence["document_kind"] for evidence in planned_evidence} == {"agenda", "minutes", "packet"}
    assert {evidence["precision"] for evidence in planned_evidence} == {"offset", "span", "section"}
    assert {evidence["document_kind"] for evidence in outcome_evidence} == {"agenda", "minutes", "packet"}
    assert {evidence["precision"] for evidence in outcome_evidence} == {"offset", "section", "file"}
    assert {evidence["document_kind"] for evidence in mismatch_evidence} == {"minutes", "packet"}
    assert {evidence["precision"] for evidence in mismatch_evidence} == {"span", "file"}


def test_st026_publication_evidence_v2_snapshot_is_stable() -> None:
    bundle = _load_fixture_bundle()
    expected_snapshot = _load_snapshot_bundle()

    assert _build_evidence_snapshot(bundle) == expected_snapshot
