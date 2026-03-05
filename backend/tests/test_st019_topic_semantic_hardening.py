from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from councilsense.app.local_pipeline import _derive_grounded_sections, _extract_phrase_topic_candidate
from councilsense.app.st017_fixture_scorecard import (
    build_gate_b_verification,
    build_scorecard,
    build_topic_semantic_gap_matrix,
    load_fixture_manifest,
    load_fixture_text,
    run_fixture_via_local_pipeline,
)
from councilsense.app.summarization import ClaimEvidencePointer, SummarizationOutput, SummaryClaim
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


def test_st019_phrase_level_topics_are_civic_and_bounded_when_sufficient_evidence() -> None:
    source_text = (
        "The Council approved a purchase agreement for right-of-way acquisition and adopted a capital improvement plan. "
        "Staff were directed to schedule a public hearing for zoning updates and transportation corridor improvements. "
        "The meeting packet included budget and water infrastructure planning details."
    )

    _, _, notable_topics = _derive_grounded_sections(source_text)

    assert 3 <= len(notable_topics) <= 5
    assert all(" " in topic for topic in notable_topics)
    lower_topics = {topic.lower() for topic in notable_topics}
    assert "approved" not in lower_topics
    assert "meeting" not in lower_topics


def test_st019_topic_semantics_fails_when_any_topic_lacks_evidence_mapping() -> None:
    output = SummarizationOutput.from_sections(
        summary="Summary",
        key_decisions=["Approved a purchase agreement."],
        key_actions=["Scheduled a public hearing for zoning updates."],
        notable_topics=[
            "Purchase agreement approval",
            "Public hearing scheduling",
            "Transportation infrastructure",
        ],
        claims=(
            SummaryClaim(
                claim_text="Approved a purchase agreement.",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact://1",
                        section_ref="minutes#L1",
                        char_start=0,
                        char_end=24,
                        excerpt="Approved a purchase agreement",
                    ),
                ),
                evidence_gap=False,
            ),
            SummaryClaim(
                claim_text="Scheduled a public hearing for zoning updates.",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact://1",
                        section_ref="minutes#L2",
                        char_start=25,
                        char_end=70,
                        excerpt="Scheduled a public hearing for zoning updates",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )

    scorecard = build_scorecard(
        manifest_path="test-manifest",
        fixtures=[],
        fixture_sources={},
        generated_at_utc=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
    )
    assert scorecard["fixture_count"] == 0

    from councilsense.app.st017_fixture_scorecard import compute_dimension_scores

    scores = compute_dimension_scores(fixture_text="fixture", output=output)
    topic_dimension = scores["topic_semantics"]

    assert topic_dimension.passed is False
    assert topic_dimension.details["failure_categories"] == {
        "generic_token": 0,
        "weak_concept_phrase": 0,
        "missing_topic_evidence_mapping": 1,
    }
    assert topic_dimension.details["unmapped_topics"] == ["transportation infrastructure"]


def test_st019_topic_suppression_tokens_are_configurable_for_phrase_derivation() -> None:
    prior = os.environ.get("COUNCILSENSE_TOPIC_SUPPRESSION_TOKENS")
    os.environ["COUNCILSENSE_TOPIC_SUPPRESSION_TOKENS"] = "expansion"
    try:
        candidate = _extract_phrase_topic_candidate(
            "The council approved the broadband expansion plan for downtown service coverage."
        )
        assert candidate == "Broadband Plan"
    finally:
        if prior is None:
            os.environ.pop("COUNCILSENSE_TOPIC_SUPPRESSION_TOKENS", None)
        else:
            os.environ["COUNCILSENSE_TOPIC_SUPPRESSION_TOKENS"] = prior


def test_st019_gap_matrix_and_gate_b_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = _repo_root()
    baseline_matrix_path = repo_root / "config" / "ops" / "st-019-topic-semantic-baseline-matrix.json"
    gate_report_path = repo_root / "docs" / "runbooks" / "st-019-topic-semantic-gate-b-verification-report.json"
    readiness_notes_path = repo_root / "docs" / "runbooks" / "st-019-topic-semantic-gate-b-readiness.md"

    assert baseline_matrix_path.exists()
    assert gate_report_path.exists()
    assert readiness_notes_path.exists()

    baseline_payload = json.loads(baseline_matrix_path.read_text(encoding="utf-8"))
    gate_payload = json.loads(gate_report_path.read_text(encoding="utf-8"))

    assert baseline_payload["schema_version"] == "st-019-topic-gap-matrix-v1"
    assert baseline_payload["fixture_count"] == 3
    assert set(baseline_payload["category_totals"].keys()) == {
        "generic_token",
        "weak_concept_phrase",
        "missing_topic_evidence_mapping",
    }

    assert gate_payload["schema_version"] == "st-017-gate-b-verification-v1"
    assert isinstance(gate_payload["gate_b_passed"], bool)
    assert len(gate_payload["fixtures"]) == 3


def test_st019_gap_matrix_generation_is_reproducible_for_unchanged_inputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    old_root = os.environ.get("COUNCILSENSE_LOCAL_ARTIFACT_ROOT")
    os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = str(artifact_root)

    try:
        connection = _init_connection()
        entries = load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())

        fixture_texts: dict[str, str] = {}
        runtime_results = []
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

        generated_at = datetime(2026, 3, 3, 11, 0, 0, tzinfo=UTC)
        scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=runtime_results,
            fixture_sources=fixture_texts,
            generated_at_utc=generated_at,
        )

        first_matrix = build_topic_semantic_gap_matrix(scorecard=scorecard, generated_at_utc=generated_at)
        second_matrix = build_topic_semantic_gap_matrix(scorecard=scorecard, generated_at_utc=generated_at)

        assert first_matrix == second_matrix

        gate_report = build_gate_b_verification(
            baseline_snapshot={
                "manifest_path": scorecard["manifest_path"],
                "scorecard": scorecard,
            },
            rerun_scorecard=scorecard,
            generated_at_utc=datetime(2026, 3, 3, 11, 5, 0, tzinfo=UTC),
        )
        assert gate_report["gate_b_passed"] is True
    finally:
        if old_root is None:
            os.environ.pop("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", None)
        else:
            os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = old_root
