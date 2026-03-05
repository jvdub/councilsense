from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from councilsense.app.meeting_bundle_planner import EXPECTED_SOURCE_TYPES, MeetingBundlePlan
from councilsense.app.source_scoped_idempotency import SourcePayloadDecision


IngestOutcome = Literal["pending", "accepted", "duplicate_suppressed", "missing", "failed"]
ExtractOutcome = Literal["pending", "processed", "missing", "failed"]
BundleReadiness = Literal["ready", "blocked"]
BundleSummaryOutcome = Literal["processed", "limited_confidence", "blocked"]


@dataclass(frozen=True)
class BundleSourceOutcomeInput:
    source_type: str
    source_id: str
    ingest_outcome: IngestOutcome
    extract_outcome: ExtractOutcome
    artifact_uri: str | None = None


@dataclass(frozen=True)
class BundleSourceState:
    source_type: str
    source_id: str | None
    source_url: str | None
    resolution: str
    ingest_outcome: IngestOutcome
    extract_outcome: ExtractOutcome
    artifact_uri: str | None


@dataclass(frozen=True)
class BundleState:
    bundle_id: str
    city_id: str
    meeting_id: str
    readiness: BundleReadiness
    summary_outcome: BundleSummaryOutcome
    reason_codes: tuple[str, ...]
    source_states: tuple[BundleSourceState, ...]


def initialize_bundle_state(*, bundle_plan: MeetingBundlePlan) -> BundleState:
    source_states: list[BundleSourceState] = []
    for source in bundle_plan.expected_sources:
        if source.resolution == "resolved":
            ingest_outcome: IngestOutcome = "pending"
            extract_outcome: ExtractOutcome = "pending"
        else:
            ingest_outcome = "missing"
            extract_outcome = "missing"

        source_states.append(
            BundleSourceState(
                source_type=source.source_type,
                source_id=source.source_id,
                source_url=source.source_url,
                resolution=source.resolution,
                ingest_outcome=ingest_outcome,
                extract_outcome=extract_outcome,
                artifact_uri=None,
            )
        )

    normalized = tuple(sorted(source_states, key=_source_state_sort_key))
    readiness, summary_outcome, reason_codes = _aggregate_bundle_outcome(source_states=normalized)
    return BundleState(
        bundle_id=bundle_plan.bundle_id,
        city_id=bundle_plan.city_id,
        meeting_id=bundle_plan.meeting_id,
        readiness=readiness,
        summary_outcome=summary_outcome,
        reason_codes=reason_codes,
        source_states=normalized,
    )


def wire_source_outcomes(
    *,
    bundle_state: BundleState,
    source_outcomes: tuple[BundleSourceOutcomeInput, ...],
) -> BundleState:
    outcome_by_type: dict[str, BundleSourceOutcomeInput] = {}
    for item in sorted(source_outcomes, key=_source_outcome_sort_key):
        outcome_by_type[item.source_type.strip().lower()] = BundleSourceOutcomeInput(
            source_type=item.source_type.strip().lower(),
            source_id=item.source_id.strip(),
            ingest_outcome=item.ingest_outcome,
            extract_outcome=item.extract_outcome,
            artifact_uri=item.artifact_uri.strip() if isinstance(item.artifact_uri, str) else None,
        )

    merged: list[BundleSourceState] = []
    for existing in bundle_state.source_states:
        event = outcome_by_type.get(existing.source_type)
        if event is None:
            merged.append(existing)
            continue

        merged.append(
            BundleSourceState(
                source_type=existing.source_type,
                source_id=existing.source_id or event.source_id,
                source_url=existing.source_url,
                resolution=existing.resolution,
                ingest_outcome=_merge_ingest_outcome(current=existing.ingest_outcome, incoming=event.ingest_outcome),
                extract_outcome=_merge_extract_outcome(current=existing.extract_outcome, incoming=event.extract_outcome),
                artifact_uri=existing.artifact_uri or event.artifact_uri,
            )
        )

    normalized = tuple(sorted(merged, key=_source_state_sort_key))
    readiness, summary_outcome, reason_codes = _aggregate_bundle_outcome(source_states=normalized)
    return BundleState(
        bundle_id=bundle_state.bundle_id,
        city_id=bundle_state.city_id,
        meeting_id=bundle_state.meeting_id,
        readiness=readiness,
        summary_outcome=summary_outcome,
        reason_codes=reason_codes,
        source_states=normalized,
    )


def source_outcome_from_dedupe_decision(
    *,
    decision: SourcePayloadDecision,
    extract_outcome: ExtractOutcome,
    artifact_uri: str | None = None,
) -> BundleSourceOutcomeInput:
    ingest_outcome: IngestOutcome = (
        "accepted" if decision.outcome == "accepted" else "duplicate_suppressed"
    )
    return BundleSourceOutcomeInput(
        source_type=decision.source_type,
        source_id=decision.source_id,
        ingest_outcome=ingest_outcome,
        extract_outcome=extract_outcome,
        artifact_uri=artifact_uri or decision.linked_artifact_uri,
    )


def _merge_ingest_outcome(*, current: IngestOutcome, incoming: IngestOutcome) -> IngestOutcome:
    return _merge_outcome(
        current=current,
        incoming=incoming,
        rank={"pending": 0, "missing": 1, "failed": 1, "duplicate_suppressed": 2, "accepted": 2},
        precedence=("accepted", "duplicate_suppressed", "failed", "missing", "pending"),
    )


def _merge_extract_outcome(*, current: ExtractOutcome, incoming: ExtractOutcome) -> ExtractOutcome:
    return _merge_outcome(
        current=current,
        incoming=incoming,
        rank={"pending": 0, "missing": 1, "failed": 1, "processed": 2},
        precedence=("processed", "failed", "missing", "pending"),
    )


def _merge_outcome(
    *,
    current: str,
    incoming: str,
    rank: dict[str, int],
    precedence: tuple[str, ...],
) -> str:
    current_rank = rank[current]
    incoming_rank = rank[incoming]
    if incoming_rank > current_rank:
        return incoming
    if incoming_rank < current_rank:
        return current

    priority = {item: index for index, item in enumerate(precedence)}
    if priority[incoming] < priority[current]:
        return incoming
    return current


def _aggregate_bundle_outcome(
    *,
    source_states: tuple[BundleSourceState, ...],
) -> tuple[BundleReadiness, BundleSummaryOutcome, tuple[str, ...]]:
    by_type = {state.source_type: state for state in source_states}
    minutes = by_type.get("minutes")
    supplemental_types = [item for item in EXPECTED_SOURCE_TYPES if item != "minutes"]
    supplemental_states = [by_type[item] for item in supplemental_types if item in by_type]
    supplemental_processed = [item for item in supplemental_states if item.extract_outcome == "processed"]

    reasons: list[str] = []

    if minutes is None or minutes.extract_outcome != "processed":
        if supplemental_processed:
            reasons.append("minutes_unavailable_using_supplemental")
            summary_outcome: BundleSummaryOutcome = "limited_confidence"
            readiness: BundleReadiness = "ready"
        else:
            reasons.append("minutes_required_for_publish")
            summary_outcome = "blocked"
            readiness = "blocked"
    else:
        summary_outcome = "processed"
        readiness = "ready"

    for state in supplemental_states:
        if state.resolution != "resolved":
            reasons.append(f"supplemental_{state.source_type}_missing_registration")
            if summary_outcome == "processed":
                summary_outcome = "limited_confidence"
            continue
        if state.extract_outcome == "processed":
            continue
        if state.extract_outcome == "failed":
            reasons.append(f"supplemental_{state.source_type}_extract_failed")
        elif state.ingest_outcome == "failed":
            reasons.append(f"supplemental_{state.source_type}_ingest_failed")
        elif state.ingest_outcome == "missing":
            reasons.append(f"supplemental_{state.source_type}_ingest_missing")
        else:
            reasons.append(f"supplemental_{state.source_type}_extract_missing")
        if summary_outcome == "processed":
            summary_outcome = "limited_confidence"

    unique_reasons = tuple(sorted(set(reasons)))
    return readiness, summary_outcome, unique_reasons


def _source_state_sort_key(source: BundleSourceState) -> tuple[int, str, str]:
    try:
        index = EXPECTED_SOURCE_TYPES.index(source.source_type)
    except ValueError:
        index = len(EXPECTED_SOURCE_TYPES)
    return (index, source.source_type, source.source_id or "")


def _source_outcome_sort_key(source: BundleSourceOutcomeInput) -> tuple[int, str, str, str, str, str]:
    source_type = source.source_type.strip().lower()
    try:
        index = EXPECTED_SOURCE_TYPES.index(source_type)
    except ValueError:
        index = len(EXPECTED_SOURCE_TYPES)
    return (
        index,
        source_type,
        source.source_id.strip(),
        source.ingest_outcome,
        source.extract_outcome,
        source.artifact_uri or "",
    )
