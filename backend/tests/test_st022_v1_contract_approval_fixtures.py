from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st022_v1_contract_approval_fixtures.json"


def _load_fixture_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path().read_text(encoding="utf-8")))


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
                    seen_document_kinds.add(str(evidence["document_kind"]))
                    precision_values.add(str(evidence["precision"]))
                    assert evidence["confidence"] in {"high", "medium", "low"}
                    assert isinstance(evidence["section_path"], str)

    assert seen_document_kinds == {"minutes", "agenda", "packet"}
    assert "offset" in precision_values
    assert "section" in precision_values
