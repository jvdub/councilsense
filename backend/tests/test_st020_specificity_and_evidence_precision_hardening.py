from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from councilsense.api.routes.meetings import (
    MeetingClaimResponse,
    MeetingEvidencePointerResponse,
    _build_evidence_references,
)
from councilsense.app.local_pipeline import _enforce_anchor_carry_through
from councilsense.app.specificity import harvest_specificity_anchors
from councilsense.app.st017_fixture_scorecard import (
    ST017_VARIANCE_BOUNDS,
    build_baseline_snapshot,
    build_gate_b_verification,
    build_scorecard,
    build_specificity_locator_gap_matrix,
    load_fixture_manifest,
    load_fixture_text,
    run_fixture_via_local_pipeline,
    FixtureRuntimeResult,
)
from councilsense.db import apply_migrations, seed_city_registry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _manifest_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st017_fixture_manifest.json"


def _init_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def _run_fixture_cohort(*, artifact_root: Path) -> tuple[dict[str, str], list[FixtureRuntimeResult]]:
    connection = _init_connection()
    entries = load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())

    fixture_texts: dict[str, str] = {}
    runtime_results: list[FixtureRuntimeResult] = []
    for entry in entries:
        text = load_fixture_text(entry=entry, repo_root=_repo_root())
        fixture_texts[entry.fixture_id] = text
        runtime_results.append(
            run_fixture_via_local_pipeline(
                connection=connection,
                entry=entry,
                fixture_text=text,
                artifact_root=artifact_root,
            )
        )
    return fixture_texts, runtime_results


def test_st020_anchor_harvesting_captures_quantitative_and_entity_signals() -> None:
    text = (
        "Riverton City Council reviewed 412 units across 96 acres and scheduled a hearing on February 12. "
        "The city engineer published a queue analysis showing peak delay 38 seconds at 13400 South."
    )

    anchors = harvest_specificity_anchors(text)
    anchor_texts = {anchor.text.lower() for anchor in anchors}
    anchor_kinds = {anchor.kind for anchor in anchors}

    assert "412 units" in anchor_texts
    assert "96 acres" in anchor_texts
    assert "february 12" in anchor_texts
    assert "Riverton City Council".lower() in anchor_texts
    assert "quantitative" in anchor_kinds
    assert "entity" in anchor_kinds


def test_st020_anchor_carry_through_enforcement_inserts_anchor_when_projection_is_sparse() -> None:
    source = "Planning staff presented 412 units across 96 acres with revised crossing requirements."

    summary, key_decisions, key_actions = _enforce_anchor_carry_through(
        source_text=source,
        summary="The council reviewed the zoning amendment.",
        key_decisions=("Approved the amendment.",),
        key_actions=("Directed planning staff to return with updates.",),
    )

    projection = " ".join((summary, *key_decisions, *key_actions)).lower()
    assert "412 units" in projection or "96 acres" in projection


def test_st020_evidence_projection_dedupes_equivalents_prefers_precise_locator_and_is_deterministic() -> None:
    claims = [
        MeetingClaimResponse(
            id="claim-1",
            claim_order=1,
            claim_text="Approved amendment.",
            evidence=[
                MeetingEvidencePointerResponse(
                    id="ptr-a",
                    artifact_id="artifact-riverton",
                    source_document_url=None,
                    section_ref="artifact.html",
                    char_start=None,
                    char_end=None,
                    excerpt="The motion passed 3-1.",
                ),
                MeetingEvidencePointerResponse(
                    id="ptr-b",
                    artifact_id="artifact-riverton",
                    source_document_url=None,
                    section_ref="minutes.section.4",
                    char_start=320,
                    char_end=346,
                    excerpt="The motion passed 3-1.",
                ),
                MeetingEvidencePointerResponse(
                    id="ptr-c",
                    artifact_id="artifact-riverton",
                    source_document_url=None,
                    section_ref="minutes.section.6",
                    char_start=401,
                    char_end=463,
                    excerpt="Planning staff will return February 12 with revised cross-sections.",
                ),
            ],
        )
    ]

    first = _build_evidence_references(claims)
    second = _build_evidence_references(claims)

    assert first == second
    assert len(first) == 2
    assert any("#minutes.section.4:320-346" in item for item in first)
    assert not any("#artifact.html:?-?" in item for item in first)


def test_st020_specificity_locator_gap_matrix_generation_is_reproducible_for_unchanged_inputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    old_root = os.environ.get("COUNCILSENSE_LOCAL_ARTIFACT_ROOT")
    os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = str(artifact_root)

    try:
        fixture_texts, runtime_results = _run_fixture_cohort(artifact_root=artifact_root / "run")
        generated_at = datetime(2026, 3, 4, 10, 0, 0, tzinfo=UTC)

        scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=runtime_results,
            fixture_sources=fixture_texts,
            generated_at_utc=generated_at,
        )
        first_matrix = build_specificity_locator_gap_matrix(scorecard=scorecard, generated_at_utc=generated_at)
        second_matrix = build_specificity_locator_gap_matrix(scorecard=scorecard, generated_at_utc=generated_at)

        assert first_matrix == second_matrix
        assert first_matrix["schema_version"] == "st-020-specificity-locator-gap-matrix-v1"
        assert first_matrix["fixture_count"] == 3
    finally:
        if old_root is None:
            os.environ.pop("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", None)
        else:
            os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = old_root


def test_st020_gate_b_verification_reports_stable_specificity_grounding_and_precision_dimensions(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    old_root = os.environ.get("COUNCILSENSE_LOCAL_ARTIFACT_ROOT")
    os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = str(artifact_root)

    try:
        baseline_sources, baseline_results = _run_fixture_cohort(artifact_root=artifact_root / "baseline")
        baseline_scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=baseline_results,
            fixture_sources=baseline_sources,
            generated_at_utc=datetime(2026, 3, 4, 11, 0, 0, tzinfo=UTC),
        )
        baseline_snapshot = build_baseline_snapshot(
            scorecard=baseline_scorecard,
            captured_by="st020-test-suite",
            captured_from="local-ci",
            captured_at_utc=datetime(2026, 3, 4, 11, 5, 0, tzinfo=UTC),
        )

        rerun_sources, rerun_results = _run_fixture_cohort(artifact_root=artifact_root / "rerun")
        rerun_scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=rerun_results,
            fixture_sources=rerun_sources,
            generated_at_utc=datetime(2026, 3, 4, 11, 10, 0, tzinfo=UTC),
        )

        gate_report = build_gate_b_verification(
            baseline_snapshot=baseline_snapshot,
            rerun_scorecard=rerun_scorecard,
            variance_bounds=ST017_VARIANCE_BOUNDS,
            generated_at_utc=datetime(2026, 3, 4, 11, 15, 0, tzinfo=UTC),
        )
        assert gate_report["gate_b_passed"] is True

        fixtures_payload = cast(list[dict[str, Any]], gate_report["fixtures"])
        for fixture in fixtures_payload:
            dimensions = {
                str(row["dimension"]): row
                for row in cast(list[dict[str, Any]], fixture["dimensions"])
            }
            assert dimensions["specificity_retention"]["stable"] is True
            assert dimensions["grounding_coverage"]["stable"] is True
            assert dimensions["evidence_count_precision"]["stable"] is True
    finally:
        if old_root is None:
            os.environ.pop("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", None)
        else:
            os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = old_root


def test_st020_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = _repo_root()
    baseline_matrix_path = repo_root / "config" / "ops" / "st-020-specificity-locator-baseline-matrix.json"
    gate_report_path = repo_root / "docs" / "runbooks" / "st-020-specificity-evidence-gate-b-verification-report.json"
    readiness_notes_path = repo_root / "docs" / "runbooks" / "st-020-specificity-evidence-gate-b-readiness.md"

    assert baseline_matrix_path.exists()
    assert gate_report_path.exists()
    assert readiness_notes_path.exists()

    baseline_payload = json.loads(baseline_matrix_path.read_text(encoding="utf-8"))
    gate_payload = json.loads(gate_report_path.read_text(encoding="utf-8"))

    assert baseline_payload["schema_version"] == "st-020-specificity-locator-gap-matrix-v1"
    assert baseline_payload["fixture_count"] == 3
    assert set(baseline_payload["category_totals"].keys()) == {
        "fixtures_with_missing_anchor_carry_through",
        "fixtures_below_majority_precise_locators",
        "fixtures_with_nonzero_grounding_gap",
    }

    assert gate_payload["schema_version"] == "st-017-gate-b-verification-v1"
    assert isinstance(gate_payload["gate_b_passed"], bool)
    assert len(gate_payload["fixtures"]) == 3
