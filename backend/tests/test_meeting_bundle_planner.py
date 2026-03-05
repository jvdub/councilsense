from __future__ import annotations

from councilsense.app.meeting_bundle_planner import (
    EXPECTED_SOURCE_TYPES,
    MeetingCandidate,
    SourceRegistration,
    plan_meeting_bundles,
)


def test_planner_resolves_expected_sources_in_canonical_order_and_reports_partial_scope() -> None:
    result = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=(
            MeetingCandidate(
                meeting_id="meeting-2026-02-11",
                title="City Council Meeting",
                candidate_url="https://example.org/meetings/2026-02-11",
                meeting_date_iso="2026-02-11",
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
                source_id="src-packet",
                source_type="packet",
                source_url="https://example.org/packet",
            ),
        ),
    )

    assert len(result.bundles) == 1
    bundle = result.bundles[0]
    assert bundle.bundle_id == "bundle:city-eagle-mountain-ut:meeting-2026-02-11"
    assert tuple(entry.source_type for entry in bundle.expected_sources) == EXPECTED_SOURCE_TYPES
    assert [entry.resolution for entry in bundle.expected_sources] == ["resolved", "missing_registration", "resolved"]

    assert any(
        diagnostic.code == "bundle_partial_source_scope"
        and diagnostic.meeting_id == "meeting-2026-02-11"
        and "agenda" in diagnostic.detail
        for diagnostic in result.diagnostics
    )


def test_planner_candidate_resolution_and_output_order_are_deterministic() -> None:
    candidates = (
        MeetingCandidate(
            meeting_id="meeting-a",
            title="Meeting A fallback",
            candidate_url="https://example.org/a-fallback",
            meeting_date_iso="",
            score=1,
        ),
        MeetingCandidate(
            meeting_id="meeting-b",
            title="Meeting B",
            candidate_url="https://example.org/b",
            meeting_date_iso="2026-01-10",
            score=4,
        ),
        MeetingCandidate(
            meeting_id="meeting-a",
            title="Meeting A primary",
            candidate_url="https://example.org/a-primary",
            meeting_date_iso="2026-02-01",
            score=2,
        ),
    )
    sources = (
        SourceRegistration(
            source_id="src-minutes",
            source_type="minutes",
            source_url="https://example.org/minutes",
        ),
    )

    first = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=candidates,
        source_registrations=sources,
    )
    second = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=tuple(reversed(candidates)),
        source_registrations=sources,
    )

    assert [bundle.meeting_id for bundle in first.bundles] == ["meeting-b", "meeting-a"]
    assert [bundle.meeting_id for bundle in second.bundles] == ["meeting-b", "meeting-a"]
    assert first.bundles == second.bundles
    assert first.diagnostics == second.diagnostics

    tie_break_diagnostics = [
        diagnostic for diagnostic in first.diagnostics if diagnostic.code == "candidate_resolution_tie_break_applied"
    ]
    assert len(tie_break_diagnostics) == 1
    assert tie_break_diagnostics[0].meeting_id == "meeting-a"
    assert "a-primary" in tie_break_diagnostics[0].detail


def test_planner_skips_candidates_when_no_expected_source_types_are_registered() -> None:
    result = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=(
            MeetingCandidate(
                meeting_id="meeting-2026-03-01",
                title="City Council Meeting",
                candidate_url="https://example.org/meetings/2026-03-01",
                meeting_date_iso="2026-03-01",
                score=3,
            ),
        ),
        source_registrations=(
            SourceRegistration(
                source_id="src-feed",
                source_type="feed",
                source_url="https://example.org/feed",
            ),
        ),
    )

    assert result.bundles == ()
    assert any(
        diagnostic.code == "candidate_skipped_no_expected_sources_registered"
        and diagnostic.meeting_id == "meeting-2026-03-01"
        for diagnostic in result.diagnostics
    )


def test_planner_rerun_with_duplicate_source_registrations_remains_deterministic() -> None:
    candidates = (
        MeetingCandidate(
            meeting_id="meeting-2026-04-03",
            title="Council Meeting B",
            candidate_url="https://example.org/meetings/b",
            meeting_date_iso="2026-04-03",
            score=2,
        ),
        MeetingCandidate(
            meeting_id="meeting-2026-04-01",
            title="Council Meeting A",
            candidate_url="https://example.org/meetings/a",
            meeting_date_iso="2026-04-01",
            score=5,
        ),
    )
    source_registrations = (
        SourceRegistration(
            source_id="src-minutes-b",
            source_type="minutes",
            source_url="https://example.org/minutes-b",
        ),
        SourceRegistration(
            source_id="src-packet",
            source_type="packet",
            source_url="https://example.org/packet",
        ),
        SourceRegistration(
            source_id="src-minutes-a",
            source_type="minutes",
            source_url="https://example.org/minutes-a",
        ),
        SourceRegistration(
            source_id="src-agenda",
            source_type="agenda",
            source_url="https://example.org/agenda",
        ),
    )

    first = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=candidates,
        source_registrations=source_registrations,
    )
    second = plan_meeting_bundles(
        city_id="city-eagle-mountain-ut",
        meeting_candidates=tuple(reversed(candidates)),
        source_registrations=tuple(reversed(source_registrations)),
    )

    assert first == second
    assert [item.meeting_id for item in first.bundles] == ["meeting-2026-04-01", "meeting-2026-04-03"]
    assert all(bundle.expected_sources[0].source_id == "src-minutes-a" for bundle in first.bundles)
    assert any(
        diagnostic.code == "source_registration_duplicate_type_resolved"
        and diagnostic.source_type == "minutes"
        and "src-minutes-a" in diagnostic.detail
        for diagnostic in first.diagnostics
    )