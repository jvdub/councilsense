from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from councilsense.app.st017_fixture_scorecard import (
    FixtureManifestEntry,
    FixtureRuntimeResult,
    build_precision_distribution_report,
    build_scorecard,
)
from councilsense.app.summarization import ClaimEvidencePointer, SummarizationOutput, SummaryClaim


def test_st026_precision_distribution_report_is_deterministic_and_captures_metadata_availability() -> None:
    generated_at = datetime(2026, 3, 7, 16, 0, 0, tzinfo=UTC)
    scorecard = build_scorecard(
        manifest_path="synthetic://st-026-precision-distribution-report",
        fixtures=[
            _fixture_result(
                fixture_id="fx-alpha-minutes",
                city_id="city-alpha",
                meeting_id="meeting-alpha-minutes",
                source_locator="fixture://alpha/minutes",
                source_type="minutes",
                output=_output_with_mixed_precision_and_unavailable_group(),
            ),
            _fixture_result(
                fixture_id="fx-alpha-agenda",
                city_id="city-alpha",
                meeting_id="meeting-alpha-agenda",
                source_locator="fixture://alpha/agenda",
                source_type="agenda",
                output=_output_with_unavailable_precision_only(),
            ),
            _fixture_result(
                fixture_id="fx-beta-packet",
                city_id="city-beta",
                meeting_id="meeting-beta-packet",
                source_locator="fixture://beta/packet",
                source_type="packet",
                output=_output_with_file_level_only(),
            ),
        ],
        fixture_sources={
            "fx-alpha-minutes": "Synthetic fixture source without harvested anchors.",
            "fx-alpha-agenda": "Synthetic fixture source without harvested anchors.",
            "fx-beta-packet": "Synthetic fixture source without harvested anchors.",
        },
        generated_at_utc=generated_at,
    )

    first = build_precision_distribution_report(scorecard=scorecard, generated_at_utc=generated_at)
    second = build_precision_distribution_report(scorecard=scorecard, generated_at_utc=generated_at)

    assert first == second
    assert first["schema_version"] == "st-026-precision-distribution-report-v1"
    assert first["fixture_count"] == 3

    run_rows = {row["fixture_id"]: row for row in first["runs"]}

    mixed = run_rows["fx-alpha-minutes"]
    assert mixed["precision_metadata_availability"] == "partial"
    assert mixed["grounded_reference_count"] == 5
    assert mixed["projected_reference_count"] == 4
    assert mixed["precision_metadata_unavailable_count"] == 1
    assert mixed["precision_class_counts"] == {
        "offset": 1,
        "span": 1,
        "section": 1,
        "file": 1,
    }
    assert mixed["precision_class_ratios"] == {
        "offset": 0.25,
        "span": 0.25,
        "section": 0.25,
        "file": 0.25,
    }
    assert mixed["finer_than_file_ratio"] == 0.75
    assert mixed["majority_finer_than_file"] is True

    unavailable = run_rows["fx-alpha-agenda"]
    assert unavailable["precision_metadata_availability"] == "unavailable"
    assert unavailable["grounded_reference_count"] == 2
    assert unavailable["projected_reference_count"] == 0
    assert unavailable["precision_metadata_unavailable_count"] == 2
    assert unavailable["finer_than_file_ratio"] is None
    assert unavailable["majority_finer_than_file_applicable"] is False

    file_only = run_rows["fx-beta-packet"]
    assert file_only["precision_metadata_availability"] == "available"
    assert file_only["precision_class_counts"] == {
        "offset": 0,
        "span": 0,
        "section": 0,
        "file": 2,
    }
    assert file_only["finer_than_file_ratio"] == 0.0
    assert file_only["majority_finer_than_file"] is False

    assert first["category_totals"] == {
        "runs_with_full_precision_metadata": 1,
        "runs_with_partial_precision_metadata": 1,
        "runs_without_precision_metadata": 1,
        "runs_without_grounded_references": 0,
        "runs_meeting_majority_finer_than_file": 1,
        "runs_below_majority_finer_than_file": 1,
    }

    assert first["run_summary"] == {
        "run_count": 3,
        "grounded_reference_count": 9,
        "projected_reference_count": 6,
        "projected_reference_ratio": 0.6667,
        "precision_metadata_unavailable_count": 3,
        "precision_class_counts": {
            "offset": 1,
            "span": 1,
            "section": 1,
            "file": 3,
        },
        "precision_class_ratios": {
            "offset": 0.1667,
            "span": 0.1667,
            "section": 0.1667,
            "file": 0.5,
        },
        "finer_than_file_count": 3,
        "finer_than_file_ratio": 0.5,
        "majority_finer_than_file_run_count": 1,
        "majority_finer_than_file_applicable_run_count": 2,
    }

    city_rows = {row["city_id"]: row for row in first["city_summaries"]}
    assert city_rows["city-alpha"] == {
        "city_id": "city-alpha",
        "run_count": 2,
        "grounded_reference_count": 7,
        "projected_reference_count": 4,
        "projected_reference_ratio": 0.5714,
        "precision_metadata_unavailable_count": 3,
        "precision_class_counts": {
            "offset": 1,
            "span": 1,
            "section": 1,
            "file": 1,
        },
        "precision_class_ratios": {
            "offset": 0.25,
            "span": 0.25,
            "section": 0.25,
            "file": 0.25,
        },
        "finer_than_file_count": 3,
        "finer_than_file_ratio": 0.75,
        "majority_finer_than_file_run_count": 1,
        "majority_finer_than_file_applicable_run_count": 1,
    }


def test_st026_precision_distribution_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "config" / "ops" / "st-026-precision-distribution-report.json"
    readiness_path = repo_root / "docs" / "runbooks" / "st-026-precision-distribution-readiness.md"

    assert report_path.exists()
    assert readiness_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "st-026-precision-distribution-report-v1"
    assert payload["fixture_count"] == 3
    assert set(payload["category_totals"].keys()) == {
        "runs_with_full_precision_metadata",
        "runs_with_partial_precision_metadata",
        "runs_without_precision_metadata",
        "runs_without_grounded_references",
        "runs_meeting_majority_finer_than_file",
        "runs_below_majority_finer_than_file",
    }
    assert {row["precision_metadata_availability"] for row in payload["runs"]} == {
        "available",
        "partial",
        "unavailable",
    }


def _fixture_result(
    *,
    fixture_id: str,
    city_id: str,
    meeting_id: str,
    source_locator: str,
    source_type: str,
    output: SummarizationOutput,
) -> FixtureRuntimeResult:
    return FixtureRuntimeResult(
        fixture=FixtureManifestEntry(
            fixture_id=fixture_id,
            city_id=city_id,
            meeting_id=meeting_id,
            meeting_uid=f"uid-{meeting_id}",
            meeting_datetime_utc="2026-03-07T16:00:00Z",
            source_locator=source_locator,
            source_type=source_type,
            structural_profile="synthetic",
            fixture_path="synthetic://st-026",
        ),
        process_status="processed",
        publication_id=f"pub-{fixture_id}",
        output=output,
    )


def _output_with_mixed_precision_and_unavailable_group() -> SummarizationOutput:
    claim_text = "Council recorded a mixed precision evidence set."
    return SummarizationOutput.from_sections(
        summary="Synthetic summary for precision distribution diagnostics.",
        key_decisions=(claim_text,),
        key_actions=(),
        notable_topics=("synthetic diagnostics",),
        claims=(
            SummaryClaim(
                claim_text=claim_text,
                evidence=(
                    _pointer(
                        artifact_id="artifact-alpha",
                        section_ref="minutes.section.1",
                        excerpt="Offset evidence excerpt.",
                        document_id="doc-minutes-1",
                        span_id="span-minutes-1",
                        document_kind="minutes",
                        section_path="minutes/section/1",
                        precision="offset",
                        confidence="high",
                        char_start=10,
                        char_end=42,
                    ),
                    _pointer(
                        artifact_id="artifact-alpha",
                        section_ref="minutes.section.2",
                        excerpt="Span evidence excerpt.",
                        document_id="doc-minutes-1",
                        span_id="span-minutes-2",
                        document_kind="minutes",
                        section_path="minutes/page/2",
                        precision="span",
                        confidence="medium",
                    ),
                    _pointer(
                        artifact_id="artifact-alpha",
                        section_ref="agenda.section.4",
                        excerpt="Section evidence excerpt.",
                        document_id="doc-agenda-1",
                        span_id="span-agenda-4",
                        document_kind="agenda",
                        section_path="agenda/section/4",
                        precision="section",
                        confidence="medium",
                    ),
                    _pointer(
                        artifact_id="artifact-alpha",
                        section_ref="artifact.html",
                        excerpt="File evidence excerpt.",
                        document_id="doc-packet-1",
                        span_id="span-packet-file",
                        document_kind="packet",
                        section_path="packet/file",
                        precision="file",
                        confidence="low",
                    ),
                    _pointer(
                        artifact_id="artifact-alpha",
                        section_ref="artifact.html",
                        excerpt="Unavailable evidence excerpt.",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )


def _output_with_unavailable_precision_only() -> SummarizationOutput:
    claim_text = "Agenda preview carried no precision metadata."
    return SummarizationOutput.from_sections(
        summary="Synthetic agenda summary without projectable evidence metadata.",
        key_decisions=(claim_text,),
        key_actions=(),
        notable_topics=("agenda preview",),
        claims=(
            SummaryClaim(
                claim_text=claim_text,
                evidence=(
                    _pointer(
                        artifact_id="artifact-agenda-preview",
                        section_ref="artifact.html",
                        excerpt="Unavailable agenda evidence one.",
                    ),
                    _pointer(
                        artifact_id="artifact-agenda-preview",
                        section_ref="artifact.html",
                        excerpt="Unavailable agenda evidence two.",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )


def _output_with_file_level_only() -> SummarizationOutput:
    claim_text = "Packet references remained file scoped."
    return SummarizationOutput.from_sections(
        summary="Synthetic packet summary with only file-level projected evidence.",
        key_decisions=(claim_text,),
        key_actions=(),
        notable_topics=("packet memo",),
        claims=(
            SummaryClaim(
                claim_text=claim_text,
                evidence=(
                    _pointer(
                        artifact_id="artifact-packet-a",
                        section_ref="artifact.html",
                        excerpt="File-only packet evidence A.",
                        document_id="doc-packet-a",
                        span_id="span-packet-a",
                        document_kind="packet",
                        section_path="packet/file",
                        precision="file",
                        confidence="low",
                    ),
                    _pointer(
                        artifact_id="artifact-packet-b",
                        section_ref="artifact.pdf",
                        excerpt="File-only packet evidence B.",
                        document_id="doc-packet-b",
                        span_id="span-packet-b",
                        document_kind="packet",
                        section_path="packet/file-2",
                        precision="file",
                        confidence="low",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )


def _pointer(
    *,
    artifact_id: str,
    section_ref: str,
    excerpt: str,
    document_id: str | None = None,
    span_id: str | None = None,
    document_kind: str | None = None,
    section_path: str | None = None,
    precision: str | None = None,
    confidence: str | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
) -> ClaimEvidencePointer:
    return ClaimEvidencePointer(
        artifact_id=artifact_id,
        section_ref=section_ref,
        char_start=char_start,
        char_end=char_end,
        excerpt=excerpt,
        document_id=document_id,
        span_id=span_id,
        document_kind=document_kind,
        section_path=section_path,
        precision=precision,
        confidence=confidence,
    )