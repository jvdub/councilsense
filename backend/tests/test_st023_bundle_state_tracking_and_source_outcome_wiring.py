from __future__ import annotations

from councilsense.app.bundle_state_tracking import (
    BundleSourceOutcomeInput,
    initialize_bundle_state,
    source_outcome_from_dedupe_decision,
    wire_source_outcomes,
)
from councilsense.app.meeting_bundle_planner import MeetingCandidate, SourceRegistration, plan_meeting_bundles
from councilsense.app.source_scoped_idempotency import SourcePayloadDecision


def test_bundle_state_full_source_success_is_ready_and_processed() -> None:
    bundle = _build_bundle(source_types=("minutes", "agenda", "packet"))
    state = initialize_bundle_state(bundle_plan=bundle)

    updated = wire_source_outcomes(
        bundle_state=state,
        source_outcomes=(
            BundleSourceOutcomeInput(
                source_type="minutes",
                source_id="src-minutes",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
            BundleSourceOutcomeInput(
                source_type="agenda",
                source_id="src-agenda",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
            BundleSourceOutcomeInput(
                source_type="packet",
                source_id="src-packet",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
        ),
    )

    assert updated.readiness == "ready"
    assert updated.summary_outcome == "processed"
    assert updated.reason_codes == ()


def test_bundle_state_minutes_plus_one_supplemental_is_ready_with_limited_confidence_reasons() -> None:
    bundle = _build_bundle(source_types=("minutes", "agenda", "packet"))
    state = initialize_bundle_state(bundle_plan=bundle)

    updated = wire_source_outcomes(
        bundle_state=state,
        source_outcomes=(
            BundleSourceOutcomeInput(
                source_type="minutes",
                source_id="src-minutes",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
            BundleSourceOutcomeInput(
                source_type="agenda",
                source_id="src-agenda",
                ingest_outcome="duplicate_suppressed",
                extract_outcome="processed",
            ),
            BundleSourceOutcomeInput(
                source_type="packet",
                source_id="src-packet",
                ingest_outcome="accepted",
                extract_outcome="failed",
            ),
        ),
    )

    assert updated.readiness == "ready"
    assert updated.summary_outcome == "limited_confidence"
    assert "supplemental_packet_extract_failed" in updated.reason_codes


def test_bundle_state_missing_minutes_is_blocked_when_no_supplemental_processed() -> None:
    bundle = _build_bundle(source_types=("minutes", "agenda", "packet"))
    state = initialize_bundle_state(bundle_plan=bundle)

    updated = wire_source_outcomes(
        bundle_state=state,
        source_outcomes=(
            BundleSourceOutcomeInput(
                source_type="minutes",
                source_id="src-minutes",
                ingest_outcome="missing",
                extract_outcome="missing",
            ),
            BundleSourceOutcomeInput(
                source_type="agenda",
                source_id="src-agenda",
                ingest_outcome="accepted",
                extract_outcome="failed",
            ),
        ),
    )

    assert updated.readiness == "blocked"
    assert updated.summary_outcome == "blocked"
    assert "minutes_required_for_publish" in updated.reason_codes


def test_bundle_state_reruns_do_not_regress_completed_source_outcomes() -> None:
    bundle = _build_bundle(source_types=("minutes", "agenda", "packet"))
    initial = initialize_bundle_state(bundle_plan=bundle)

    first_pass = wire_source_outcomes(
        bundle_state=initial,
        source_outcomes=(
            BundleSourceOutcomeInput(
                source_type="minutes",
                source_id="src-minutes",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
            BundleSourceOutcomeInput(
                source_type="agenda",
                source_id="src-agenda",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
        ),
    )

    rerun = wire_source_outcomes(
        bundle_state=first_pass,
        source_outcomes=(
            BundleSourceOutcomeInput(
                source_type="minutes",
                source_id="src-minutes",
                ingest_outcome="duplicate_suppressed",
                extract_outcome="missing",
            ),
            BundleSourceOutcomeInput(
                source_type="agenda",
                source_id="src-agenda",
                ingest_outcome="failed",
                extract_outcome="failed",
            ),
            BundleSourceOutcomeInput(
                source_type="packet",
                source_id="src-packet",
                ingest_outcome="accepted",
                extract_outcome="processed",
            ),
        ),
    )

    source_by_type = {item.source_type: item for item in rerun.source_states}
    assert source_by_type["minutes"].extract_outcome == "processed"
    assert source_by_type["agenda"].extract_outcome == "processed"
    assert source_by_type["minutes"].ingest_outcome == "accepted"
    assert rerun.readiness == "ready"
    assert rerun.summary_outcome == "processed"


def test_source_outcome_wiring_from_dedupe_decision_maps_ingest_branch() -> None:
    decision = SourcePayloadDecision(
        source_id="src-agenda",
        source_type="agenda",
        source_revision="rev-1",
        source_checksum="sha256:abc",
        idempotency_key="idem",
        dedupe_key="dedupe",
        outcome="duplicate_suppressed",
        linked_artifact_uri="s3://bucket/agenda/1.txt",
    )

    mapped = source_outcome_from_dedupe_decision(
        decision=decision,
        extract_outcome="processed",
    )

    assert mapped.source_type == "agenda"
    assert mapped.ingest_outcome == "duplicate_suppressed"
    assert mapped.extract_outcome == "processed"
    assert mapped.artifact_uri == "s3://bucket/agenda/1.txt"


def _build_bundle(*, source_types: tuple[str, ...]):
    registrations = tuple(
        SourceRegistration(
            source_id=f"src-{source_type}",
            source_type=source_type,
            source_url=f"https://example.org/{source_type}",
        )
        for source_type in source_types
    )
    result = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=(
            MeetingCandidate(
                meeting_id="meeting-2026-03-04-regular",
                title="City Council Meeting",
                candidate_url="https://example.org/meetings/2026-03-04",
                meeting_date_iso="2026-03-04",
                score=10,
            ),
        ),
        source_registrations=registrations,
    )
    assert len(result.bundles) == 1
    return result.bundles[0]
