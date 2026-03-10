from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from councilsense.app.local_pipeline import LlmProviderConfig, LocalPipelineOrchestrator
from councilsense.app.specificity import anchor_present_in_projection, harvest_specificity_anchors
from councilsense.app.summarization import ClaimEvidencePointer, SummarizationOutput, SummaryClaim
from councilsense.db import MeetingWriteRepository


SCORECARD_SCHEMA_VERSION = "st-017-fixture-scorecard-v1"
RUBRIC_VERSION = "st-017-rubric-v1"
BASELINE_SCHEMA_VERSION = "st-017-fixture-baseline-v1"
GATE_B_SCHEMA_VERSION = "st-017-gate-b-verification-v1"
TOPIC_GAP_MATRIX_SCHEMA_VERSION = "st-019-topic-gap-matrix-v1"
SPECIFICITY_LOCATOR_GAP_MATRIX_SCHEMA_VERSION = "st-020-specificity-locator-gap-matrix-v1"
PRECISION_DISTRIBUTION_REPORT_SCHEMA_VERSION = "st-026-precision-distribution-report-v1"

_PRECISION_CLASSES = ("offset", "span", "section", "file")

GENERIC_TOPIC_TOKENS = frozenset(
    {
        "approved",
        "approve",
        "agreement",
        "purchase",
        "item",
        "meeting",
        "minutes",
        "agenda",
        "scheduled",
    }
)
_TOPIC_CIVIC_TERMS = frozenset(
    {
        "budget",
        "fiscal",
        "zoning",
        "land",
        "hearing",
        "ordinance",
        "resolution",
        "agreement",
        "contract",
        "transportation",
        "traffic",
        "water",
        "wastewater",
        "utility",
        "road",
        "street",
        "public",
        "safety",
        "annexation",
        "housing",
        "development",
        "capital",
        "improvement",
        "title",
        "procurement",
        "infrastructure",
        "planning",
    }
)
_TOPIC_CIVIC_PHRASES = frozenset(
    {
        "purchase agreement",
        "public hearing",
        "right-of-way",
        "land use",
        "capital improvement",
        "development agreement",
        "title transfer",
        "roadway improvement",
        "utility infrastructure",
        "transportation infrastructure",
        "budget planning",
    }
)


@dataclass(frozen=True)
class St017ParityThresholds:
    section_completeness_min: float = 1.0
    topic_semantics_min: float = 0.5
    specificity_retention_min: float = 1.0
    grounding_coverage_min: float = 1.0
    evidence_count_precision_min: float = 0.5
    minimum_evidence_count: int = 3


@dataclass(frozen=True)
class St017VarianceBounds:
    section_completeness_max_delta: float = 0.0
    topic_semantics_max_delta: float = 0.0
    specificity_retention_max_delta: float = 0.0
    grounding_coverage_max_delta: float = 0.0
    evidence_count_precision_max_delta: float = 0.0


ST017_PARITY_THRESHOLDS = St017ParityThresholds()
ST017_VARIANCE_BOUNDS = St017VarianceBounds()


@dataclass(frozen=True)
class FixtureManifestEntry:
    fixture_id: str
    city_id: str
    meeting_id: str
    meeting_uid: str
    meeting_datetime_utc: str
    source_locator: str
    source_type: str
    structural_profile: str
    fixture_path: str

    @property
    def stable_fixture_key(self) -> str:
        digest = hashlib.sha256(
            "|".join((self.city_id, self.meeting_datetime_utc, self.source_locator)).encode("utf-8")
        ).hexdigest()
        return f"fx-{digest[:16]}"


@dataclass(frozen=True)
class FixtureRuntimeResult:
    fixture: FixtureManifestEntry
    process_status: str
    publication_id: str
    output: SummarizationOutput


@dataclass(frozen=True)
class DimensionScore:
    score: float
    threshold: float
    passed: bool
    details: dict[str, object]


def load_fixture_manifest(*, manifest_path: Path, repo_root: Path) -> tuple[FixtureManifestEntry, ...]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("fixtures")
    if not isinstance(raw_entries, list):
        raise ValueError("ST-017 fixture manifest must include a list at 'fixtures'.")

    entries: list[FixtureManifestEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("Fixture manifest entries must be objects.")
        entry = FixtureManifestEntry(
            fixture_id=str(raw.get("fixture_id") or "").strip(),
            city_id=str(raw.get("city_id") or "").strip(),
            meeting_id=str(raw.get("meeting_id") or "").strip(),
            meeting_uid=str(raw.get("meeting_uid") or "").strip(),
            meeting_datetime_utc=str(raw.get("meeting_datetime_utc") or "").strip(),
            source_locator=str(raw.get("source_locator") or "").strip(),
            source_type=str(raw.get("source_type") or "").strip(),
            structural_profile=str(raw.get("structural_profile") or "").strip(),
            fixture_path=str(raw.get("fixture_path") or "").strip(),
        )
        _validate_manifest_entry(entry=entry, manifest_path=manifest_path, repo_root=repo_root)
        entries.append(entry)

    fixture_ids = [entry.fixture_id for entry in entries]
    if len(set(fixture_ids)) != len(fixture_ids):
        raise ValueError("ST-017 fixture manifest contains duplicate fixture_id values.")

    meeting_ids = [entry.meeting_id for entry in entries]
    if len(set(meeting_ids)) != len(meeting_ids):
        raise ValueError("ST-017 fixture manifest contains duplicate meeting_id values.")

    if len(entries) < 3:
        raise ValueError("ST-017 fixture manifest must include Eagle Mountain + two comparison fixtures.")

    eagle_entries = [
        entry for entry in entries if entry.city_id == "city-eagle-mountain-ut" and entry.meeting_datetime_utc.startswith("2024-12-03")
    ]
    if not eagle_entries:
        raise ValueError("ST-017 fixture manifest must include Eagle Mountain meeting date 2024-12-03.")

    structural_profiles = {entry.structural_profile for entry in entries}
    if len(structural_profiles) < 3:
        raise ValueError("ST-017 fixture manifest must include three structurally distinct fixture profiles.")

    return tuple(
        sorted(
            entries,
            key=lambda item: (
                item.meeting_datetime_utc,
                item.city_id,
                item.meeting_id,
                item.fixture_id,
            ),
        )
    )


def _validate_manifest_entry(*, entry: FixtureManifestEntry, manifest_path: Path, repo_root: Path) -> None:
    required_fields = (
        entry.fixture_id,
        entry.city_id,
        entry.meeting_id,
        entry.meeting_uid,
        entry.meeting_datetime_utc,
        entry.source_locator,
        entry.source_type,
        entry.structural_profile,
        entry.fixture_path,
    )
    if any(not field for field in required_fields):
        raise ValueError(f"Fixture entry has blank required fields in {manifest_path}.")

    resolved_fixture = repo_root / entry.fixture_path
    if not resolved_fixture.exists():
        raise ValueError(f"Fixture file is missing for {entry.fixture_id}: {entry.fixture_path}")


def load_fixture_text(*, entry: FixtureManifestEntry, repo_root: Path) -> str:
    path = repo_root / entry.fixture_path
    return path.read_text(encoding="utf-8")


def run_fixture_via_local_pipeline(
    *,
    connection: sqlite3.Connection,
    entry: FixtureManifestEntry,
    fixture_text: str,
    artifact_root: Path,
) -> FixtureRuntimeResult:
    write_repository = MeetingWriteRepository(connection)
    write_repository.upsert_meeting(
        meeting_id=entry.meeting_id,
        meeting_uid=entry.meeting_uid,
        city_id=entry.city_id,
        title=f"ST-017 fixture {entry.fixture_id}",
    )

    city_dir = artifact_root / entry.city_id
    city_dir.mkdir(parents=True, exist_ok=True)
    meeting_prefix = entry.meeting_id.removeprefix("meeting-")
    artifact_path = city_dir / f"{meeting_prefix}-{entry.stable_fixture_key}.txt"
    artifact_path.write_text(fixture_text, encoding="utf-8")

    orchestrator = LocalPipelineOrchestrator(connection)
    run_id = f"run-st017-{entry.stable_fixture_key}-{uuid.uuid4().hex[:6]}"
    process_result = orchestrator.process_latest(
        run_id=run_id,
        city_id=entry.city_id,
        meeting_id=entry.meeting_id,
        ingest_stage_metadata={
            "source_id": entry.source_locator,
            "artifact_path": str(artifact_path),
            "fixture_id": entry.fixture_id,
        },
        llm_config=LlmProviderConfig(provider="none", timeout_seconds=20.0),
    )

    publication_row = connection.execute(
        """
        SELECT id, summary_text, key_decisions_json, key_actions_json, notable_topics_json
        FROM summary_publications
        WHERE meeting_id = ?
        ORDER BY version_no DESC, published_at DESC, id DESC
        LIMIT 1
        """,
        (entry.meeting_id,),
    ).fetchone()
    if publication_row is None:
        raise ValueError(f"No publication row was produced for fixture {entry.fixture_id}.")

    publication_id = str(publication_row[0])
    claims = _load_publication_claims(connection=connection, publication_id=publication_id)
    output = SummarizationOutput.from_sections(
        summary=str(publication_row[1]),
        key_decisions=_read_json_array(publication_row[2]),
        key_actions=_read_json_array(publication_row[3]),
        notable_topics=_read_json_array(publication_row[4]),
        claims=claims,
    )

    return FixtureRuntimeResult(
        fixture=entry,
        process_status=process_result.status,
        publication_id=publication_id,
        output=output,
    )


def _read_json_array(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str):
        return ()
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        return ()
    values = [str(item).strip() for item in parsed if str(item).strip()]
    return tuple(values)


def _load_publication_claims(*, connection: sqlite3.Connection, publication_id: str) -> tuple[SummaryClaim, ...]:
    claim_rows = connection.execute(
        """
        SELECT id, claim_text
        FROM publication_claims
        WHERE publication_id = ?
        ORDER BY claim_order ASC, id ASC
        """,
        (publication_id,),
    ).fetchall()

    claims: list[SummaryClaim] = []
    for claim_row in claim_rows:
        claim_id = str(claim_row[0])
        pointer_rows = connection.execute(
            """
            SELECT
                artifact_id,
                section_ref,
                char_start,
                char_end,
                excerpt,
                document_id,
                span_id,
                document_kind,
                section_path,
                precision,
                confidence
            FROM claim_evidence_pointers
            WHERE claim_id = ?
            ORDER BY id ASC
            """,
            (claim_id,),
        ).fetchall()
        pointers = tuple(
            ClaimEvidencePointer(
                artifact_id=str(row[0]),
                section_ref=(str(row[1]) if row[1] is not None else None),
                char_start=(int(row[2]) if row[2] is not None else None),
                char_end=(int(row[3]) if row[3] is not None else None),
                excerpt=str(row[4]),
                document_id=(str(row[5]) if row[5] is not None else None),
                span_id=(str(row[6]) if row[6] is not None else None),
                document_kind=(str(row[7]) if row[7] is not None else None),
                section_path=(str(row[8]) if row[8] is not None else None),
                precision=(str(row[9]) if row[9] is not None else None),
                confidence=(str(row[10]) if row[10] is not None else None),
            )
            for row in pointer_rows
        )
        claims.append(
            SummaryClaim(
                claim_text=str(claim_row[1]),
                evidence=pointers,
                evidence_gap=(len(pointers) == 0),
            )
        )
    return tuple(claims)


def compute_dimension_scores(
    *,
    fixture_text: str,
    output: SummarizationOutput,
    thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS,
) -> dict[str, DimensionScore]:
    section_score = _section_completeness_score(output)
    topic_score, topic_details = _topic_semantics_score(output)
    specificity_score, specificity_details = _specificity_retention_score(fixture_text=fixture_text, output=output)
    grounding_score, grounding_details = _grounding_coverage_score(output)
    evidence_score, evidence_details = _evidence_count_precision_score(output=output, min_evidence_count=thresholds.minimum_evidence_count)

    return {
        "section_completeness": DimensionScore(
            score=section_score,
            threshold=thresholds.section_completeness_min,
            passed=section_score >= thresholds.section_completeness_min,
            details={},
        ),
        "topic_semantics": DimensionScore(
            score=topic_score,
            threshold=thresholds.topic_semantics_min,
            passed=topic_score >= thresholds.topic_semantics_min,
            details=topic_details,
        ),
        "specificity_retention": DimensionScore(
            score=specificity_score,
            threshold=thresholds.specificity_retention_min,
            passed=specificity_score >= thresholds.specificity_retention_min,
            details=specificity_details,
        ),
        "grounding_coverage": DimensionScore(
            score=grounding_score,
            threshold=thresholds.grounding_coverage_min,
            passed=grounding_score >= thresholds.grounding_coverage_min,
            details=grounding_details,
        ),
        "evidence_count_precision": DimensionScore(
            score=evidence_score,
            threshold=thresholds.evidence_count_precision_min,
            passed=evidence_score >= thresholds.evidence_count_precision_min,
            details=evidence_details,
        ),
    }


def assert_section_completeness(score: float, *, thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS) -> None:
    _assert_dimension_threshold("section_completeness", score, thresholds.section_completeness_min)


def assert_topic_semantics(score: float, *, thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS) -> None:
    _assert_dimension_threshold("topic_semantics", score, thresholds.topic_semantics_min)


def assert_specificity_retention(score: float, *, thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS) -> None:
    _assert_dimension_threshold("specificity_retention", score, thresholds.specificity_retention_min)


def assert_grounding_coverage(score: float, *, thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS) -> None:
    _assert_dimension_threshold("grounding_coverage", score, thresholds.grounding_coverage_min)


def assert_evidence_count_precision(score: float, *, thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS) -> None:
    _assert_dimension_threshold("evidence_count_precision", score, thresholds.evidence_count_precision_min)


def assert_parity_dimensions(scores: dict[str, DimensionScore]) -> None:
    for dimension, payload in scores.items():
        _assert_dimension_threshold(dimension, payload.score, payload.threshold)


def _assert_dimension_threshold(dimension: str, score: float, threshold: float) -> None:
    if score < threshold:
        raise AssertionError(f"{dimension} below frozen threshold: score={score:.4f}, threshold={threshold:.4f}")


def _section_completeness_score(output: SummarizationOutput) -> float:
    required = {
        "summary": bool(output.summary.strip()),
        "key_decisions": len(output.key_decisions) > 0,
        "key_actions": len(output.key_actions) > 0,
        "notable_topics": len(output.notable_topics) > 0,
        "evidence_references": _count_unique_evidence_pointers(output) > 0,
    }
    return sum(1 for passed in required.values() if passed) / len(required)


def _topic_semantics_score(output: SummarizationOutput) -> tuple[float, dict[str, object]]:
    topics = [topic.strip().lower() for topic in output.notable_topics if topic.strip()]
    if not topics:
        return 0.0, {
            "semantic_topics": 0,
            "total_topics": 0,
            "failure_categories": {
                "generic_token": 0,
                "weak_concept_phrase": 0,
                "missing_topic_evidence_mapping": 0,
            },
        }

    generic_topics = [topic for topic in topics if _is_generic_topic(topic)]
    weak_concept_topics = [
        topic
        for topic in topics
        if topic not in generic_topics and not _is_civic_concept_topic(topic)
    ]
    semantic_topics = [
        topic
        for topic in topics
        if topic not in generic_topics and topic not in weak_concept_topics
    ]
    mapping = _topic_evidence_mapping_details(output=output, topics=topics)
    missing_mappings = cast(list[str], mapping["unmapped_topics"])

    if missing_mappings:
        score = 0.0
    else:
        score = len(semantic_topics) / len(topics)

    return score, {
        "semantic_topics": len(semantic_topics),
        "total_topics": len(topics),
        "topics": topics,
        "generic_topics": generic_topics,
        "weak_concept_topics": weak_concept_topics,
        "topic_count": len(topics),
        "bounded_3_to_5": 3 <= len(topics) <= 5,
        "mapped_topic_count": mapping["mapped_topic_count"],
        "unmapped_topics": missing_mappings,
        "mapping_coverage": mapping["mapping_coverage"],
        "failure_categories": {
            "generic_token": len(generic_topics),
            "weak_concept_phrase": len(weak_concept_topics),
            "missing_topic_evidence_mapping": len(missing_mappings),
        },
    }


def _is_generic_topic(topic: str) -> bool:
    tokens = _tokenize_topic_terms(topic)
    if not tokens:
        return True
    return all(token in GENERIC_TOPIC_TOKENS for token in tokens)


def _is_civic_concept_topic(topic: str) -> bool:
    lowered = topic.lower()
    if any(phrase in lowered for phrase in _TOPIC_CIVIC_PHRASES):
        return True

    tokens = _tokenize_topic_terms(topic)
    if not tokens:
        return False
    non_generic = [token for token in tokens if token not in GENERIC_TOPIC_TOKENS]
    if len(non_generic) < 2:
        return False
    return any(token in _TOPIC_CIVIC_TERMS for token in non_generic)


def _topic_evidence_mapping_details(*, output: SummarizationOutput, topics: list[str]) -> dict[str, object]:
    evidence_claim_terms: list[set[str]] = []
    for claim in output.claims:
        if not claim.evidence:
            continue
        evidence_claim_terms.append(_tokenize_topic_terms(claim.claim_text))

    mapped_topics: list[str] = []
    unmapped_topics: list[str] = []
    for topic in topics:
        topic_terms = {
            token
            for token in _tokenize_topic_terms(topic)
            if token not in GENERIC_TOPIC_TOKENS
        }
        if not topic_terms:
            unmapped_topics.append(topic)
            continue

        mapped = any(_topic_terms_overlap(topic_terms, claim_terms) for claim_terms in evidence_claim_terms)
        if mapped:
            mapped_topics.append(topic)
        else:
            unmapped_topics.append(topic)

    total_topics = len(topics)
    mapping_coverage = (len(mapped_topics) / total_topics) if total_topics else 0.0
    return {
        "mapped_topics": mapped_topics,
        "unmapped_topics": unmapped_topics,
        "mapped_topic_count": len(mapped_topics),
        "mapping_coverage": mapping_coverage,
    }


def _tokenize_topic_terms(value: str) -> set[str]:
    return {
        _normalize_semantic_token(token)
        for token in re.findall(r"[a-z][a-z\-]{2,}", value.lower())
        if token not in {"the", "and", "for", "with", "from", "into", "onto", "city", "council"}
        and _normalize_semantic_token(token)
    }


def _topic_terms_overlap(topic_terms: set[str], claim_terms: set[str]) -> bool:
    if topic_terms & claim_terms:
        return True

    for topic_term in topic_terms:
        for claim_term in claim_terms:
            if _tokens_semantically_match(topic_term, claim_term):
                return True
    return False


def _tokens_semantically_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if left.startswith(right) and len(right) >= 5:
        return True
    if right.startswith(left) and len(left) >= 5:
        return True
    return False


def _normalize_semantic_token(token: str) -> str:
    normalized = token.strip().lower()
    if len(normalized) <= 4:
        return normalized

    for suffix in ("ing", "edly", "ed", "es", "s"):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _specificity_retention_score(*, fixture_text: str, output: SummarizationOutput) -> tuple[float, dict[str, object]]:
    harvested = harvest_specificity_anchors(fixture_text)
    anchors = [anchor.normalized for anchor in harvested]
    if not anchors:
        return 1.0, {
            "anchor_count": 0,
            "retained_anchor_count": 0,
            "anchors": [],
            "retained": [],
            "anchor_breakdown": {},
        }

    projection_haystack = " ".join((output.summary, *output.key_decisions, *output.key_actions))
    retained = [anchor.normalized for anchor in harvested if anchor_present_in_projection(anchor, projection_haystack)]
    score = 1.0 if retained else 0.0
    breakdown: dict[str, int] = {}
    for anchor in harvested:
        breakdown[anchor.kind] = breakdown.get(anchor.kind, 0) + 1

    return score, {
        "anchor_count": len(anchors),
        "retained_anchor_count": len(retained),
        "anchors": anchors,
        "retained": retained,
        "anchor_breakdown": breakdown,
    }


def _grounding_coverage_score(output: SummarizationOutput) -> tuple[float, dict[str, object]]:
    findings = [*output.key_decisions, *output.key_actions]
    if not findings:
        return 0.0, {"finding_count": 0, "covered_findings": 0}

    covered = 0
    claim_index = {claim.claim_text.strip().lower(): claim for claim in output.claims}
    for finding in findings:
        claim = claim_index.get(finding.strip().lower())
        if claim is not None and claim.evidence:
            covered += 1

    score = covered / len(findings)
    return score, {"finding_count": len(findings), "covered_findings": covered}


def _evidence_count_precision_score(*, output: SummarizationOutput, min_evidence_count: int) -> tuple[float, dict[str, object]]:
    pointers = _list_unique_pointers(output)
    evidence_count = len(pointers)
    count_ratio = min(1.0, evidence_count / float(max(min_evidence_count, 1)))

    precise_count = 0
    for pointer in pointers:
        has_offsets = pointer.char_start is not None and pointer.char_end is not None
        section_ref = (pointer.section_ref or "").lower()
        has_precise_section_ref = section_ref not in {"", "artifact.html", "artifact.pdf", "meeting.metadata"}
        if has_offsets or has_precise_section_ref:
            precise_count += 1

    precision_ratio = precise_count / evidence_count if evidence_count else 0.0
    score = (count_ratio + precision_ratio) / 2.0
    precision_distribution = _build_precision_distribution_details(output=output)
    return score, {
        "evidence_pointer_count": evidence_count,
        "precision_ratio": precision_ratio,
        "precise_pointer_count": precise_count,
        "minimum_evidence_count": min_evidence_count,
        **precision_distribution,
    }


def _count_unique_evidence_pointers(output: SummarizationOutput) -> int:
    return len(_list_unique_pointers(output))


def _list_unique_pointers(output: SummarizationOutput) -> tuple[ClaimEvidencePointer, ...]:
    seen: set[tuple[str, str | None, int | None, int | None, str]] = set()
    unique: list[ClaimEvidencePointer] = []
    for claim in output.claims:
        for pointer in claim.evidence:
            key = (pointer.artifact_id, pointer.section_ref, pointer.char_start, pointer.char_end, pointer.excerpt)
            if key in seen:
                continue
            seen.add(key)
            unique.append(pointer)
    return tuple(unique)


def _build_precision_distribution_details(*, output: SummarizationOutput) -> dict[str, object]:
    groups = _group_pointers_by_reference(output=output)
    projected = _select_projected_precision_pointers(groups=groups)

    grounded_reference_count = len(groups)
    projected_reference_count = len(projected)
    metadata_unavailable_count = grounded_reference_count - projected_reference_count

    counts = {precision: 0 for precision in _PRECISION_CLASSES}
    for pointer in projected:
        precision = _normalized_precision(pointer.precision)
        if precision is None:
            continue
        counts[precision] += 1

    if grounded_reference_count == 0:
        availability = "none"
    elif projected_reference_count == 0:
        availability = "unavailable"
    elif projected_reference_count == grounded_reference_count:
        availability = "available"
    else:
        availability = "partial"

    finer_than_file_count = counts["offset"] + counts["span"] + counts["section"]
    projected_ratios = {
        precision: round((count / projected_reference_count), 4) if projected_reference_count else 0.0
        for precision, count in counts.items()
    }
    finer_than_file_ratio = round((finer_than_file_count / projected_reference_count), 4) if projected_reference_count else None
    metadata_coverage_ratio = round((projected_reference_count / grounded_reference_count), 4) if grounded_reference_count else 0.0

    return {
        "grounded_reference_count": grounded_reference_count,
        "projected_reference_count": projected_reference_count,
        "projected_reference_ratio": metadata_coverage_ratio,
        "precision_metadata_unavailable_count": metadata_unavailable_count,
        "precision_metadata_availability": availability,
        "precision_class_counts": counts,
        "precision_class_ratios": projected_ratios,
        "finer_than_file_count": finer_than_file_count,
        "finer_than_file_ratio": finer_than_file_ratio,
        "majority_finer_than_file_applicable": projected_reference_count > 0,
        "majority_finer_than_file": (finer_than_file_ratio is not None and finer_than_file_ratio > 0.5),
    }


def _group_pointers_by_reference(*, output: SummarizationOutput) -> dict[tuple[str, str], list[ClaimEvidencePointer]]:
    groups: dict[tuple[str, str], list[ClaimEvidencePointer]] = {}
    for claim in output.claims:
        for pointer in claim.evidence:
            key = (pointer.artifact_id, _normalize_reference_text(pointer.excerpt))
            groups.setdefault(key, []).append(pointer)
    return groups


def _select_projected_precision_pointers(
    *,
    groups: dict[tuple[str, str], list[ClaimEvidencePointer]],
) -> tuple[ClaimEvidencePointer, ...]:
    projected: list[ClaimEvidencePointer] = []
    for key in sorted(groups):
        candidates = [pointer for pointer in groups[key] if _supports_precision_projection(pointer)]
        if not candidates:
            continue
        projected.append(sorted(candidates, key=_pointer_preference_key)[0])

    return tuple(sorted(projected, key=_pointer_order_key))


def _normalize_reference_text(value: str) -> str:
    return " ".join(value.lower().split())


def _normalized_precision(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized == "document":
        normalized = "file"
    if normalized in _PRECISION_CLASSES:
        return normalized
    return None


def _supports_precision_projection(pointer: ClaimEvidencePointer) -> bool:
    return all(
        value is not None and value.strip()
        for value in (pointer.document_kind, pointer.section_path)
    ) and _normalized_precision(pointer.precision) is not None


def _pointer_precision_rank(pointer: ClaimEvidencePointer) -> int:
    precision = _normalized_precision(pointer.precision)
    if precision is not None:
        return _PRECISION_CLASSES.index(precision)
    return len(_PRECISION_CLASSES)


def _pointer_metadata_completeness(pointer: ClaimEvidencePointer) -> int:
    score = 0
    for value in (
        pointer.document_id,
        pointer.span_id,
        pointer.document_kind,
        pointer.section_path,
        pointer.precision,
        pointer.confidence,
        pointer.section_ref,
    ):
        if value is not None and value.strip():
            score += 1
    if pointer.char_start is not None:
        score += 1
    if pointer.char_end is not None:
        score += 1
    return score


def _stable_pointer_section(pointer: ClaimEvidencePointer) -> str:
    return ((pointer.section_path or pointer.section_ref) or "").strip().lower()


def _pointer_preference_key(pointer: ClaimEvidencePointer) -> tuple[int, int, str, int, int, str, str]:
    return (
        _pointer_precision_rank(pointer),
        -_pointer_metadata_completeness(pointer),
        _stable_pointer_section(pointer),
        pointer.char_start if pointer.char_start is not None else 10**9,
        pointer.char_end if pointer.char_end is not None else 10**9,
        _normalize_reference_text(pointer.excerpt),
        pointer.artifact_id,
    )


def _pointer_order_key(pointer: ClaimEvidencePointer) -> tuple[int, str, str, str, int, int, str]:
    return (
        _pointer_precision_rank(pointer),
        (pointer.document_kind or "").strip().lower(),
        pointer.artifact_id,
        _stable_pointer_section(pointer),
        pointer.char_start if pointer.char_start is not None else 10**9,
        pointer.char_end if pointer.char_end is not None else 10**9,
        _normalize_reference_text(pointer.excerpt),
    )


def build_scorecard(
    *,
    manifest_path: str,
    fixtures: list[FixtureRuntimeResult],
    fixture_sources: dict[str, str],
    generated_at_utc: datetime | None = None,
    rubric_version: str = RUBRIC_VERSION,
    thresholds: St017ParityThresholds = ST017_PARITY_THRESHOLDS,
) -> dict[str, object]:
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    ordered = sorted(fixtures, key=lambda item: item.fixture.fixture_id)

    fixture_rows: list[dict[str, object]] = []
    for item in ordered:
        scores = compute_dimension_scores(
            fixture_text=fixture_sources[item.fixture.fixture_id],
            output=item.output,
            thresholds=thresholds,
        )
        fixture_rows.append(
            {
                "fixture_id": item.fixture.fixture_id,
                "stable_fixture_key": item.fixture.stable_fixture_key,
                "city_id": item.fixture.city_id,
                "meeting_id": item.fixture.meeting_id,
                "meeting_datetime_utc": item.fixture.meeting_datetime_utc,
                "source_locator": item.fixture.source_locator,
                "source_type": item.fixture.source_type,
                "structural_profile": item.fixture.structural_profile,
                "process_status": item.process_status,
                "dimensions": {
                    name: {
                        "score": round(payload.score, 4),
                        "threshold": payload.threshold,
                        "passed": payload.passed,
                        "details": payload.details,
                    }
                    for name, payload in scores.items()
                },
            }
        )

    return {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "rubric_version": rubric_version,
        "manifest_path": manifest_path,
        "generated_at_utc": timestamp,
        "fixture_count": len(fixture_rows),
        "fixtures": fixture_rows,
    }


def serialize_scorecard(scorecard: dict[str, object]) -> str:
    return f"{json.dumps(scorecard, indent=2, sort_keys=True)}\n"


def write_scorecard(path: Path, scorecard: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_scorecard(scorecard), encoding="utf-8")


def build_topic_semantic_gap_matrix(
    *,
    scorecard: dict[str, object],
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    fixture_rows = _read_scorecard_fixture_rows(cast_payload=scorecard)

    matrix_rows: list[dict[str, object]] = []
    category_totals = {
        "generic_token": 0,
        "weak_concept_phrase": 0,
        "missing_topic_evidence_mapping": 0,
    }

    for row in fixture_rows:
        fixture_id = str(row.get("fixture_id") or "")
        dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
        topic_payload = dimensions.get("topic_semantics") if isinstance(dimensions, dict) else {}
        details = topic_payload.get("details") if isinstance(topic_payload, dict) else {}
        details_obj = details if isinstance(details, dict) else {}
        category_counts = details_obj.get("failure_categories")
        if not isinstance(category_counts, dict):
            category_counts = {
                "generic_token": 0,
                "weak_concept_phrase": 0,
                "missing_topic_evidence_mapping": 0,
            }

        generic_examples: list[object] = []
        weak_examples: list[object] = []
        mapping_examples: list[object] = []
        if isinstance(details_obj.get("generic_topics"), list):
            generic_examples = cast(list[object], details_obj.get("generic_topics"))
        if isinstance(details_obj.get("weak_concept_topics"), list):
            weak_examples = cast(list[object], details_obj.get("weak_concept_topics"))
        if isinstance(details_obj.get("unmapped_topics"), list):
            mapping_examples = cast(list[object], details_obj.get("unmapped_topics"))

        generic_count = int(category_counts.get("generic_token", 0))
        weak_count = int(category_counts.get("weak_concept_phrase", 0))
        mapping_count = int(category_counts.get("missing_topic_evidence_mapping", 0))

        category_totals["generic_token"] += generic_count
        category_totals["weak_concept_phrase"] += weak_count
        category_totals["missing_topic_evidence_mapping"] += mapping_count

        matrix_rows.append(
            {
                "fixture_id": fixture_id,
                "failure_categories": {
                    "generic_token": {
                        "count": generic_count,
                        "examples": [str(value) for value in generic_examples[:2]],
                    },
                    "weak_concept_phrase": {
                        "count": weak_count,
                        "examples": [str(value) for value in weak_examples[:2]],
                    },
                    "missing_topic_evidence_mapping": {
                        "count": mapping_count,
                        "examples": [str(value) for value in mapping_examples[:2]],
                    },
                },
            }
        )

    return {
        "schema_version": TOPIC_GAP_MATRIX_SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "rubric_version": scorecard.get("rubric_version"),
        "manifest_path": scorecard.get("manifest_path"),
        "fixture_count": len(matrix_rows),
        "category_totals": category_totals,
        "fixtures": matrix_rows,
    }


def serialize_topic_semantic_gap_matrix(matrix: dict[str, object]) -> str:
    return f"{json.dumps(matrix, indent=2, sort_keys=True)}\n"


def build_specificity_locator_gap_matrix(
    *,
    scorecard: dict[str, object],
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    fixture_rows = _read_scorecard_fixture_rows(cast_payload=scorecard)

    matrix_rows: list[dict[str, object]] = []
    totals = {
        "fixtures_with_missing_anchor_carry_through": 0,
        "fixtures_below_majority_precise_locators": 0,
        "fixtures_with_nonzero_grounding_gap": 0,
    }

    for row in fixture_rows:
        fixture_id = str(row.get("fixture_id") or "")
        dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}

        specificity = dimensions.get("specificity_retention") if isinstance(dimensions, dict) else {}
        specificity_details = specificity.get("details") if isinstance(specificity, dict) else {}
        evidence = dimensions.get("evidence_count_precision") if isinstance(dimensions, dict) else {}
        evidence_details = evidence.get("details") if isinstance(evidence, dict) else {}
        grounding = dimensions.get("grounding_coverage") if isinstance(dimensions, dict) else {}
        grounding_details = grounding.get("details") if isinstance(grounding, dict) else {}

        anchor_count = int((specificity_details.get("anchor_count") if isinstance(specificity_details, dict) else 0) or 0)
        retained_anchor_count = int(
            (specificity_details.get("retained_anchor_count") if isinstance(specificity_details, dict) else 0) or 0
        )
        precise_pointer_count = int(
            (evidence_details.get("precise_pointer_count") if isinstance(evidence_details, dict) else 0) or 0
        )
        evidence_pointer_count = int(
            (evidence_details.get("evidence_pointer_count") if isinstance(evidence_details, dict) else 0) or 0
        )
        precision_ratio = float((evidence_details.get("precision_ratio") if isinstance(evidence_details, dict) else 0.0) or 0.0)
        covered_findings = int((grounding_details.get("covered_findings") if isinstance(grounding_details, dict) else 0) or 0)
        finding_count = int((grounding_details.get("finding_count") if isinstance(grounding_details, dict) else 0) or 0)

        missing_anchor = anchor_count > 0 and retained_anchor_count <= 0
        low_precision = evidence_pointer_count > 0 and precision_ratio < 0.5
        grounding_gap = finding_count > 0 and covered_findings < finding_count
        if missing_anchor:
            totals["fixtures_with_missing_anchor_carry_through"] += 1
        if low_precision:
            totals["fixtures_below_majority_precise_locators"] += 1
        if grounding_gap:
            totals["fixtures_with_nonzero_grounding_gap"] += 1

        matrix_rows.append(
            {
                "fixture_id": fixture_id,
                "anchor_metrics": {
                    "anchor_count": anchor_count,
                    "retained_anchor_count": retained_anchor_count,
                    "missing_anchor_carry_through": missing_anchor,
                    "anchor_breakdown": (
                        specificity_details.get("anchor_breakdown") if isinstance(specificity_details, dict) else {}
                    ),
                },
                "evidence_locator_metrics": {
                    "evidence_pointer_count": evidence_pointer_count,
                    "precise_pointer_count": precise_pointer_count,
                    "precision_ratio": precision_ratio,
                    "majority_precise_locators": precision_ratio >= 0.5,
                },
                "grounding_metrics": {
                    "finding_count": finding_count,
                    "covered_findings": covered_findings,
                    "full_grounding_coverage": covered_findings >= finding_count and finding_count > 0,
                },
            }
        )

    return {
        "schema_version": SPECIFICITY_LOCATOR_GAP_MATRIX_SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "rubric_version": scorecard.get("rubric_version"),
        "manifest_path": scorecard.get("manifest_path"),
        "fixture_count": len(matrix_rows),
        "category_totals": totals,
        "fixtures": matrix_rows,
    }


def serialize_specificity_locator_gap_matrix(matrix: dict[str, object]) -> str:
    return f"{json.dumps(matrix, indent=2, sort_keys=True)}\n"


def build_precision_distribution_report(
    *,
    scorecard: dict[str, object],
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    fixture_rows = sorted(
        _read_scorecard_fixture_rows(cast_payload=scorecard),
        key=lambda row: (
            str(row.get("city_id") or ""),
            str(row.get("source_type") or ""),
            str(row.get("source_locator") or ""),
            str(row.get("fixture_id") or ""),
        ),
    )

    run_rows: list[dict[str, object]] = []
    city_groups: dict[str, list[dict[str, object]]] = {}
    source_groups: dict[str, list[dict[str, object]]] = {}
    city_source_groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    category_totals = {
        "runs_with_full_precision_metadata": 0,
        "runs_with_partial_precision_metadata": 0,
        "runs_without_precision_metadata": 0,
        "runs_without_grounded_references": 0,
        "runs_meeting_majority_finer_than_file": 0,
        "runs_below_majority_finer_than_file": 0,
    }

    for row in fixture_rows:
        dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
        evidence = dimensions.get("evidence_count_precision") if isinstance(dimensions, dict) else {}
        details = evidence.get("details") if isinstance(evidence, dict) else {}
        metrics = _read_precision_distribution_metrics(details if isinstance(details, dict) else {})

        run_row = {
            "fixture_id": str(row.get("fixture_id") or ""),
            "city_id": str(row.get("city_id") or ""),
            "meeting_id": str(row.get("meeting_id") or ""),
            "source_type": str(row.get("source_type") or ""),
            "source_locator": str(row.get("source_locator") or ""),
            "process_status": str(row.get("process_status") or ""),
            **metrics,
        }
        run_rows.append(run_row)

        city_id = str(run_row["city_id"])
        source_type = str(run_row["source_type"])
        city_groups.setdefault(city_id, []).append(run_row)
        source_groups.setdefault(source_type, []).append(run_row)
        city_source_groups.setdefault((city_id, source_type), []).append(run_row)

        availability = str(metrics["precision_metadata_availability"])
        if availability == "available":
            category_totals["runs_with_full_precision_metadata"] += 1
        elif availability == "partial":
            category_totals["runs_with_partial_precision_metadata"] += 1
        elif availability == "unavailable":
            category_totals["runs_without_precision_metadata"] += 1
        else:
            category_totals["runs_without_grounded_references"] += 1

        if bool(metrics["majority_finer_than_file"]):
            category_totals["runs_meeting_majority_finer_than_file"] += 1
        elif bool(metrics["majority_finer_than_file_applicable"]):
            category_totals["runs_below_majority_finer_than_file"] += 1

    return {
        "schema_version": PRECISION_DISTRIBUTION_REPORT_SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "rubric_version": scorecard.get("rubric_version"),
        "manifest_path": scorecard.get("manifest_path"),
        "fixture_count": len(run_rows),
        "category_totals": category_totals,
        "run_summary": _aggregate_precision_distribution(rows=run_rows),
        "city_summaries": [
            {
                "city_id": city_id,
                **_aggregate_precision_distribution(rows=rows),
            }
            for city_id, rows in sorted(city_groups.items())
        ],
        "source_summaries": [
            {
                "source_type": source_type,
                **_aggregate_precision_distribution(rows=rows),
            }
            for source_type, rows in sorted(source_groups.items())
        ],
        "city_source_summaries": [
            {
                "city_id": city_id,
                "source_type": source_type,
                **_aggregate_precision_distribution(rows=rows),
            }
            for (city_id, source_type), rows in sorted(city_source_groups.items())
        ],
        "runs": run_rows,
    }


def serialize_precision_distribution_report(report: dict[str, object]) -> str:
    return f"{json.dumps(report, indent=2, sort_keys=True)}\n"


def _read_precision_distribution_metrics(details: dict[str, object]) -> dict[str, object]:
    counts_raw = details.get("precision_class_counts") if isinstance(details.get("precision_class_counts"), dict) else {}
    ratios_raw = details.get("precision_class_ratios") if isinstance(details.get("precision_class_ratios"), dict) else {}

    counts = {precision: int(counts_raw.get(precision, 0) or 0) for precision in _PRECISION_CLASSES}
    ratios = {precision: float(ratios_raw.get(precision, 0.0) or 0.0) for precision in _PRECISION_CLASSES}

    finer_than_file_ratio = details.get("finer_than_file_ratio")
    return {
        "grounded_reference_count": int(details.get("grounded_reference_count", 0) or 0),
        "projected_reference_count": int(details.get("projected_reference_count", 0) or 0),
        "projected_reference_ratio": float(details.get("projected_reference_ratio", 0.0) or 0.0),
        "precision_metadata_unavailable_count": int(details.get("precision_metadata_unavailable_count", 0) or 0),
        "precision_metadata_availability": str(details.get("precision_metadata_availability") or "none"),
        "precision_class_counts": counts,
        "precision_class_ratios": ratios,
        "finer_than_file_count": int(details.get("finer_than_file_count", 0) or 0),
        "finer_than_file_ratio": (float(finer_than_file_ratio) if finer_than_file_ratio is not None else None),
        "majority_finer_than_file_applicable": bool(details.get("majority_finer_than_file_applicable", False)),
        "majority_finer_than_file": bool(details.get("majority_finer_than_file", False)),
    }


def _aggregate_precision_distribution(*, rows: list[dict[str, object]]) -> dict[str, object]:
    counts = {precision: 0 for precision in _PRECISION_CLASSES}
    grounded_reference_count = 0
    projected_reference_count = 0
    metadata_unavailable_count = 0
    run_count = len(rows)
    majority_met = 0
    majority_applicable = 0

    for row in rows:
        grounded_reference_count += int(row.get("grounded_reference_count", 0) or 0)
        projected_reference_count += int(row.get("projected_reference_count", 0) or 0)
        metadata_unavailable_count += int(row.get("precision_metadata_unavailable_count", 0) or 0)
        row_counts = row.get("precision_class_counts") if isinstance(row.get("precision_class_counts"), dict) else {}
        for precision in _PRECISION_CLASSES:
            counts[precision] += int(row_counts.get(precision, 0) or 0)
        if bool(row.get("majority_finer_than_file_applicable", False)):
            majority_applicable += 1
        if bool(row.get("majority_finer_than_file", False)):
            majority_met += 1

    finer_than_file_count = counts["offset"] + counts["span"] + counts["section"]
    ratios = {
        precision: round((count / projected_reference_count), 4) if projected_reference_count else 0.0
        for precision, count in counts.items()
    }
    finer_than_file_ratio = round((finer_than_file_count / projected_reference_count), 4) if projected_reference_count else None
    projected_reference_ratio = round((projected_reference_count / grounded_reference_count), 4) if grounded_reference_count else 0.0

    return {
        "run_count": run_count,
        "grounded_reference_count": grounded_reference_count,
        "projected_reference_count": projected_reference_count,
        "projected_reference_ratio": projected_reference_ratio,
        "precision_metadata_unavailable_count": metadata_unavailable_count,
        "precision_class_counts": counts,
        "precision_class_ratios": ratios,
        "finer_than_file_count": finer_than_file_count,
        "finer_than_file_ratio": finer_than_file_ratio,
        "majority_finer_than_file_run_count": majority_met,
        "majority_finer_than_file_applicable_run_count": majority_applicable,
    }


def build_baseline_snapshot(
    *,
    scorecard: dict[str, object],
    captured_by: str,
    captured_from: str,
    captured_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = (captured_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "rubric_version": scorecard["rubric_version"],
        "captured_at_utc": timestamp,
        "captured_by": captured_by,
        "captured_from": captured_from,
        "manifest_path": scorecard["manifest_path"],
        "fixture_count": scorecard["fixture_count"],
        "scorecard": scorecard,
    }


def build_gate_b_verification(
    *,
    baseline_snapshot: dict[str, object],
    rerun_scorecard: dict[str, object],
    variance_bounds: St017VarianceBounds = ST017_VARIANCE_BOUNDS,
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()
    baseline_fixtures = {
        str(item["fixture_id"]): item
        for item in _read_scorecard_fixture_rows(cast_payload=baseline_snapshot["scorecard"])
    }
    rerun_fixtures = {
        str(item["fixture_id"]): item
        for item in _read_scorecard_fixture_rows(cast_payload=rerun_scorecard)
    }

    drift_rows: list[dict[str, object]] = []
    gate_passed = True
    for fixture_id in sorted(rerun_fixtures):
        baseline = baseline_fixtures.get(fixture_id)
        current = rerun_fixtures[fixture_id]
        if baseline is None:
            gate_passed = False
            drift_rows.append(
                {
                    "fixture_id": fixture_id,
                    "status": "missing_baseline_fixture",
                    "dimensions": [],
                }
            )
            continue

        baseline_dimensions = baseline.get("dimensions") if isinstance(baseline, dict) else None
        current_dimensions = current.get("dimensions") if isinstance(current, dict) else None
        if not isinstance(baseline_dimensions, dict) or not isinstance(current_dimensions, dict):
            gate_passed = False
            drift_rows.append(
                {
                    "fixture_id": fixture_id,
                    "status": "invalid_dimension_payload",
                    "dimensions": [],
                }
            )
            continue

        row_dimensions: list[dict[str, object]] = []
        for dimension_name in sorted(current_dimensions):
            baseline_dimension = baseline_dimensions.get(dimension_name)
            current_dimension = current_dimensions.get(dimension_name)
            if not isinstance(baseline_dimension, dict) or not isinstance(current_dimension, dict):
                gate_passed = False
                row_dimensions.append(
                    {
                        "dimension": dimension_name,
                        "status": "invalid_dimension_payload",
                    }
                )
                continue

            baseline_score = float(baseline_dimension.get("score", 0.0))
            current_score = float(current_dimension.get("score", 0.0))
            baseline_pass = bool(baseline_dimension.get("passed", False))
            current_pass = bool(current_dimension.get("passed", False))
            delta = round(abs(current_score - baseline_score), 6)
            allowed_delta = _variance_bound_for_dimension(dimension_name, variance_bounds)
            pass_flip = baseline_pass != current_pass
            in_bounds = delta <= allowed_delta
            stable = (not pass_flip) and in_bounds
            if not stable:
                gate_passed = False

            row_dimensions.append(
                {
                    "dimension": dimension_name,
                    "baseline_score": baseline_score,
                    "rerun_score": current_score,
                    "delta": delta,
                    "allowed_delta": allowed_delta,
                    "baseline_passed": baseline_pass,
                    "rerun_passed": current_pass,
                    "pass_fail_flip": pass_flip,
                    "stable": stable,
                }
            )

        drift_rows.append(
            {
                "fixture_id": fixture_id,
                "status": "ok",
                "dimensions": row_dimensions,
            }
        )

    return {
        "schema_version": GATE_B_SCHEMA_VERSION,
        "rubric_version": rerun_scorecard["rubric_version"],
        "generated_at_utc": timestamp,
        "baseline_manifest_path": baseline_snapshot["manifest_path"],
        "rerun_manifest_path": rerun_scorecard["manifest_path"],
        "gate_b_passed": gate_passed,
        "fixtures": drift_rows,
    }


def _variance_bound_for_dimension(dimension_name: str, bounds: St017VarianceBounds) -> float:
    mapping = {
        "section_completeness": bounds.section_completeness_max_delta,
        "topic_semantics": bounds.topic_semantics_max_delta,
        "specificity_retention": bounds.specificity_retention_max_delta,
        "grounding_coverage": bounds.grounding_coverage_max_delta,
        "evidence_count_precision": bounds.evidence_count_precision_max_delta,
    }
    return float(mapping.get(dimension_name, 0.0))


def _read_scorecard_fixture_rows(*, cast_payload: object) -> list[dict[str, object]]:
    if not isinstance(cast_payload, dict):
        return []
    fixtures = cast_payload.get("fixtures")
    if not isinstance(fixtures, list):
        return []
    return [row for row in fixtures if isinstance(row, dict)]