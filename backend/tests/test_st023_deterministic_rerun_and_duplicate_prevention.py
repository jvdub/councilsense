from __future__ import annotations

from dataclasses import dataclass

from councilsense.app.bundle_state_tracking import (
    BundleState,
    initialize_bundle_state,
    source_outcome_from_dedupe_decision,
    wire_source_outcomes,
)
from councilsense.app.meeting_bundle_planner import MeetingCandidate, SourceRegistration, plan_meeting_bundles
from councilsense.app.source_scoped_idempotency import (
    SourcePayloadCandidate,
    SourcePayloadDedupeDiagnostic,
    dedupe_source_payloads,
)


@dataclass(frozen=True)
class _WindowEffects:
    created_documents: int
    created_artifacts: int
    created_publications: int
    bundle_state: BundleState


def test_st023_repeated_ingest_window_with_same_payloads_is_idempotent_for_documents_artifacts_and_publication() -> None:
    city_id = "city-eagle-mountain-ut"
    meeting_id = "meeting-2026-03-12-regular"
    bundle = _build_bundle(city_id=city_id, meeting_id=meeting_id)

    payloads = (
        SourcePayloadCandidate(
            source_id="src-minutes",
            source_type="minutes",
            source_url="https://example.org/minutes",
            source_revision="rev-2026-03-12T19:00:00Z",
            source_checksum="sha256:minutes-2026-03-12",
            artifact_uri="s3://fixtures/st023/minutes-2026-03-12.txt",
        ),
        SourcePayloadCandidate(
            source_id="src-agenda",
            source_type="agenda",
            source_url="https://example.org/agenda",
            source_revision="rev-2026-03-12T19:00:00Z",
            source_checksum="sha256:agenda-2026-03-12",
            artifact_uri="s3://fixtures/st023/agenda-2026-03-12.txt",
        ),
        SourcePayloadCandidate(
            source_id="src-packet",
            source_type="packet",
            source_url="https://example.org/packet",
            source_revision="rev-2026-03-12T19:00:00Z",
            source_checksum="sha256:packet-2026-03-12",
            artifact_uri="s3://fixtures/st023/packet-2026-03-12.txt",
        ),
    )

    seen_documents: set[str] = set()
    seen_artifacts: set[str] = set()
    seen_publications: set[str] = set()
    state = initialize_bundle_state(bundle_plan=bundle)

    first_window = _apply_ingest_window(
        city_id=city_id,
        meeting_id=meeting_id,
        bundle_state=state,
        payloads=payloads,
        seen_documents=seen_documents,
        seen_artifacts=seen_artifacts,
        seen_publications=seen_publications,
    )
    second_window = _apply_ingest_window(
        city_id=city_id,
        meeting_id=meeting_id,
        bundle_state=first_window.bundle_state,
        payloads=tuple(reversed(payloads)),
        seen_documents=seen_documents,
        seen_artifacts=seen_artifacts,
        seen_publications=seen_publications,
    )

    assert first_window.created_documents == 3
    assert first_window.created_artifacts == 3
    assert first_window.created_publications == 1

    assert second_window.created_documents == 0
    assert second_window.created_artifacts == 0
    assert second_window.created_publications == 0
    assert second_window.bundle_state.readiness == "ready"
    assert second_window.bundle_state.summary_outcome == "processed"


def test_st023_duplicate_payload_suppression_diagnostics_identify_bundle_and_source_context() -> None:
    city_id = "city-eagle-mountain-ut"
    meeting_id = "meeting-2026-03-12-regular"

    result = dedupe_source_payloads(
        city_id=city_id,
        meeting_id=meeting_id,
        candidates=(
            SourcePayloadCandidate(
                source_id="src-minutes-primary",
                source_type="minutes",
                source_url="https://example.org/minutes-primary",
                source_revision="rev-2026-03-12T19:00:00Z",
                source_checksum="sha256:minutes-2026-03-12",
                artifact_uri="s3://fixtures/st023/minutes-primary.txt",
            ),
            SourcePayloadCandidate(
                source_id="src-minutes-secondary",
                source_type="minutes",
                source_url="https://example.org/minutes-secondary",
                source_revision="rev-2026-03-12T19:00:00Z",
                source_checksum="sha256:minutes-2026-03-12",
                artifact_uri="s3://fixtures/st023/minutes-secondary.txt",
            ),
            SourcePayloadCandidate(
                source_id="src-agenda",
                source_type="agenda",
                source_url="https://example.org/agenda",
                source_revision="rev-2026-03-12T19:00:00Z",
                source_checksum="sha256:agenda-2026-03-12",
                artifact_uri="s3://fixtures/st023/agenda.txt",
            ),
        ),
    )

    assert len(result.accepted) == 2
    assert len(result.suppressed) == 1
    suppressed = result.suppressed[0]

    assert suppressed.outcome == "duplicate_suppressed"
    assert suppressed.linked_artifact_uri == "s3://fixtures/st023/minutes-primary.txt"

    diagnostic = _find_duplicate_diagnostic(diagnostics=result.diagnostics)
    assert diagnostic.city_id == city_id
    assert diagnostic.meeting_id == meeting_id
    assert diagnostic.source_type == "minutes"
    assert diagnostic.source_id == "src-minutes-secondary"
    assert diagnostic.outcome == "duplicate_suppressed"
    assert diagnostic.idempotency_key == suppressed.idempotency_key
    assert diagnostic.dedupe_key == suppressed.dedupe_key
    assert "duplicate payload suppressed" in diagnostic.detail


def _apply_ingest_window(
    *,
    city_id: str,
    meeting_id: str,
    bundle_state: BundleState,
    payloads: tuple[SourcePayloadCandidate, ...],
    seen_documents: set[str],
    seen_artifacts: set[str],
    seen_publications: set[str],
) -> _WindowEffects:
    dedupe_result = dedupe_source_payloads(
        city_id=city_id,
        meeting_id=meeting_id,
        candidates=payloads,
    )

    created_documents = 0
    created_artifacts = 0
    outcomes = []
    for decision in (*dedupe_result.accepted, *dedupe_result.suppressed):
        if decision.idempotency_key not in seen_documents:
            seen_documents.add(decision.idempotency_key)
            created_documents += 1
        if decision.linked_artifact_uri and decision.linked_artifact_uri not in seen_artifacts:
            seen_artifacts.add(decision.linked_artifact_uri)
            created_artifacts += 1
        outcomes.append(
            source_outcome_from_dedupe_decision(
                decision=decision,
                extract_outcome="processed",
            )
        )

    next_state = wire_source_outcomes(
        bundle_state=bundle_state,
        source_outcomes=tuple(outcomes),
    )

    created_publications = 0
    if next_state.readiness == "ready" and next_state.bundle_id not in seen_publications:
        seen_publications.add(next_state.bundle_id)
        created_publications = 1

    return _WindowEffects(
        created_documents=created_documents,
        created_artifacts=created_artifacts,
        created_publications=created_publications,
        bundle_state=next_state,
    )


def _build_bundle(*, city_id: str, meeting_id: str):
    result = plan_meeting_bundles(
        city_id=city_id,
        meeting_candidates=(
            MeetingCandidate(
                meeting_id=meeting_id,
                title="City Council Regular Meeting",
                candidate_url=f"https://example.org/meetings/{meeting_id}",
                meeting_date_iso="2026-03-12",
                score=10,
            ),
        ),
        source_registrations=(
            SourceRegistration(
                source_id="src-minutes",
                source_type="minutes",
                source_url="https://example.org/minutes",
            ),
            SourceRegistration(
                source_id="src-agenda",
                source_type="agenda",
                source_url="https://example.org/agenda",
            ),
            SourceRegistration(
                source_id="src-packet",
                source_type="packet",
                source_url="https://example.org/packet",
            ),
        ),
    )
    assert len(result.bundles) == 1
    return result.bundles[0]


def _find_duplicate_diagnostic(*, diagnostics: tuple[SourcePayloadDedupeDiagnostic, ...]) -> SourcePayloadDedupeDiagnostic:
    matches = [item for item in diagnostics if item.code == "source_payload_duplicate_suppressed"]
    assert len(matches) == 1
    return matches[0]