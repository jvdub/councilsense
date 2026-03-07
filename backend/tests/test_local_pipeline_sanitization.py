from __future__ import annotations

from councilsense.app.local_pipeline import (
    _AuthorityConflictSignal,
    _AuthorityPolicyResult,
    _MeetingMaterialContext,
    _apply_material_context,
    _evaluate_authority_policy,
    _build_grounded_summary,
    _build_claims_from_findings,
    _derive_grounded_sections,
    _focus_source_text,
    _normalize_action_sentence,
    _normalize_decision_sentence,
    _normalize_generated_text,
)
from councilsense.app.multi_document_compose import ComposedSourceDocument, SourceCoverageSummary, SummarizeComposeInput


def test_normalize_generated_text_removes_think_blocks() -> None:
    raw = "Visible start <think>hidden chain of thought</think> visible end"
    normalized = _normalize_generated_text(raw)

    assert "hidden chain of thought" not in normalized
    assert "Visible start" in normalized
    assert "visible end" in normalized


def test_derive_grounded_sections_excludes_provider_terms_from_topics() -> None:
    source_text = (
        "City Council approved the transportation budget and directed staff to publish the timeline. "
        "Public hearing was scheduled for zoning updates. "
        "The local runtime should not appear as a topic and ollama should not appear either."
    )

    key_decisions, key_actions, notable_topics = _derive_grounded_sections(source_text)

    assert len(key_decisions) >= 1
    assert len(key_actions) >= 1
    assert "local" not in notable_topics
    assert "runtime" not in notable_topics
    assert "ollama" not in notable_topics


def test_focus_source_text_removes_attendance_blocks() -> None:
    source_text = (
        "ELECTED OFFICIALS PRESENT: Mayor Pro Tempore and Councilmembers. "
        "CITY STAFF PRESENT: Department staff list with many names. "
        "A motion was approved to adopt the downtown plan."
    )

    focused = _focus_source_text(source_text)

    assert "ELECTED OFFICIALS PRESENT" not in focused
    assert "CITY STAFF PRESENT" not in focused
    assert "motion was approved" in focused.lower()


def test_build_grounded_summary_prefers_substantive_outcomes_over_operations() -> None:
    source_text = (
        "Mayor Westmoreland was excused, and Councilmember Gray joined as Mayor Pro Tempore at 4:20 PM. "
        "The Council approved a purchase agreement for right-of-way acquisition. "
        "The Council approved the 2025 meeting schedule with additional November and December dates."
    )

    summary = _build_grounded_summary(source_text)

    assert "joined as Mayor Pro Tempore" not in summary
    assert "4:20 PM" not in summary
    assert "approved a purchase agreement" in summary.lower()


def test_apply_material_context_converts_agenda_only_meeting_to_preview_mode() -> None:
    source_text = (
        "PUBLIC HEARINGS ONLY 3.A. PUBLIC HEARING/NO ACTION TAKEN - A Public Hearing to Allow Public Input Regarding "
        "the Issuance and Sale of Not More Than $220,000,000 Aggregate Principal Amount of Water & Sewer Revenue Bonds, Series 2026. "
        "RESOLUTIONS 4.A. RESOLUTION - A Resolution of Eagle Mountain City, Utah, Authorizing Related Bond Documents. "
        "BACKGROUND: At the February 17, 2026 City Council meeting, the City Council adopted a resolution authorizing issuance."
    )

    summary, key_decisions, key_actions, notable_topics = _apply_material_context(
        source_text=source_text,
        summary="The council approved bond documents.",
        key_decisions=("Approved bond documents.",),
        key_actions=("Adopted the related resolution.",),
        notable_topics=("Resolution Approval", "Water and Utility Infrastructure"),
        material_context=_MeetingMaterialContext(
            document_kind="agenda",
            meeting_date_iso="2026-03-05",
            meeting_temporal_status="same_day_or_future",
        ),
        authority_policy=_AuthorityPolicyResult(
            authority_outcome="agenda_preview_only",
            publication_status="limited_confidence",
            reason_codes=("agenda_preview_only", "missing_authoritative_minutes"),
            summarize_text=source_text,
            authoritative_source_type=None,
            outcome_source_types=("agenda",),
            preview_only=True,
            conflicts=(),
        ),
    )

    assert "preview scheduled items" in summary.lower()
    assert "no decisions or completed actions are recorded yet" in summary.lower()
    assert key_decisions == ()
    assert key_actions == ()
    assert "Resolution Agenda Items" in notable_topics
    assert all(len(topic.split()) <= 6 for topic in notable_topics)


def test_evaluate_authority_policy_prefers_minutes_and_flags_conflicting_supporting_sources() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                source_type="minutes",
                text="Council adopted Ordinance 2026-12 on second reading. Staff will publish the adopted ordinance before April 1.",
            ),
            _compose_source(
                source_type="agenda",
                text="Public hearing and possible action on proposed Ordinance 2026-12.",
            ),
            _compose_source(
                source_type="packet",
                text="Staff recommended continuing Ordinance 2026-12 to a later meeting if amendments were requested.",
            ),
        ),
        statuses={"minutes": "present", "agenda": "present", "packet": "present"},
    )

    policy = _evaluate_authority_policy(compose_input=compose_input)

    assert policy.authority_outcome == "minutes_authoritative"
    assert policy.publication_status == "processed"
    assert policy.reason_codes == ()
    assert policy.summarize_text.startswith("Council adopted Ordinance 2026-12")
    assert policy.outcome_source_types == ("minutes",)
    assert policy.conflicts == (
        _AuthorityConflictSignal(
            authoritative_source_type="minutes",
            conflicting_source_type="packet",
            subject="ordinance 2026-12",
            authoritative_action="approve",
            conflicting_action="continue",
            authoritative_finding="Council adopted Ordinance 2026-12 on second reading.",
            conflicting_finding="Staff recommended continuing Ordinance 2026-12 to a later meeting if amendments were requested.",
            resolution="authoritative_override",
        ),
    )


def test_evaluate_authority_policy_marks_unresolved_conflict_without_minutes() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                source_type="agenda",
                text="Consider adoption of Resolution 2026-09 awarding the Main Street paving contract.",
            ),
            _compose_source(
                source_type="packet",
                text="Staff recommendation was to continue Resolution 2026-09 pending updated bids.",
            ),
        ),
        statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
    )

    policy = _evaluate_authority_policy(compose_input=compose_input)

    assert policy.authority_outcome == "unresolved_conflict"
    assert policy.publication_status == "limited_confidence"
    assert policy.reason_codes == ("missing_authoritative_minutes", "unresolved_source_conflict")
    assert policy.preview_only is True
    assert policy.outcome_source_types == ("agenda", "packet")
    assert len(policy.conflicts) == 1
    assert policy.conflicts[0].subject == "resolution 2026-09"


def test_evaluate_authority_policy_downgrades_when_minutes_are_only_source_coverage() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                source_type="minutes",
                text="Council approved the fiscal year transfer and directed staff to finalize the interfund memo.",
            ),
        ),
        statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
    )

    policy = _evaluate_authority_policy(compose_input=compose_input)

    assert policy.authority_outcome == "supplemental_coverage_missing"
    assert policy.publication_status == "limited_confidence"
    assert policy.reason_codes == ("supplemental_sources_missing",)
    assert policy.summarize_text.startswith("Council approved the fiscal year transfer")


def test_derive_grounded_sections_excludes_city_name_topics() -> None:
    source_text = (
        "Eagle Mountain City Council approved a motion to adopt the transportation plan. "
        "The Council directed staff to schedule a public hearing for zoning updates. "
        "Residents discussed traffic and infrastructure improvements."
    )

    _, _, notable_topics = _derive_grounded_sections(source_text)

    assert "eagle" not in notable_topics
    assert "mountain" not in notable_topics


def test_normalize_decision_sentence_rewrites_resolution_to_outcome() -> None:
    source = (
        "RESOLUTION - A Resolution of Eagle Mountain City, Utah, Approving a Purchase "
        "Agreement with Ivory Land Corporation for the Acquisition of Right-of-Way."
    )

    normalized = _normalize_decision_sentence(source)

    assert normalized.startswith("Approved a Purchase Agreement")


def test_actions_prefer_action_not_location_description() -> None:
    source_text = (
        "The property is located directly east of the wastewater treatment plant, Utah County Parcel Number 59:018:0049. "
        "The Council determined to remove this item from the Consent Agenda and place it as a scheduled item for further discussion."
    )

    _, key_actions, _ = _derive_grounded_sections(source_text)

    assert any("decided to remove the agenda item" in action.lower() for action in key_actions)
    assert all("parcel number" not in action.lower() for action in key_actions)


def test_normalize_action_sentence_rewrites_determined_phrase() -> None:
    source = "The Council determined to remove this item from the Consent Agenda."

    normalized = _normalize_action_sentence(source)

    assert normalized.startswith("The Council decided to")
    assert "this item" not in normalized.lower()


def test_build_claims_from_findings_returns_multiple_claims() -> None:
    claims = _build_claims_from_findings(
        key_decisions=("Approved the purchase agreement.", "Consented to the transfer of title."),
        key_actions=("Approved the 2025 meeting schedule.",),
        source_text=(
            "The Council approved the purchase agreement. "
            "The Council consented to transfer of title. "
            "The Council approved the 2025 meeting schedule."
        ),
        artifact_id="artifact-local:test.txt",
        section_ref="artifact.txt",
        fallback_claim="Fallback claim",
    )

    assert len(claims) >= 3


def test_build_claims_from_findings_prefers_sentence_level_locator_and_offsets() -> None:
    claims = _build_claims_from_findings(
        key_decisions=("Approved a zoning amendment with a 25-foot transition requirement.",),
        key_actions=("Directed planning staff to return on February 12.",),
        source_text=(
            "Roll call completed at 6:00 PM. "
            "The motion passed 3-1 with a 25-foot transition requirement. "
            "Planning staff will return on February 12 with revised cross-sections."
        ),
        artifact_id="artifact-local:test.txt",
        section_ref="artifact.html",
        fallback_claim="Fallback claim",
    )

    assert claims
    pointer = claims[0].evidence[0]
    assert pointer.section_ref is not None
    assert ".sentence." in pointer.section_ref
    assert pointer.char_start is not None
    assert pointer.char_end is not None


def _build_compose_input(
    *,
    sources: tuple[ComposedSourceDocument, ...],
    statuses: dict[str, str],
) -> SummarizeComposeInput:
    return SummarizeComposeInput(
        meeting_id="meeting-test",
        source_order=("minutes", "agenda", "packet"),
        sources=sources,
        composed_text="\n\n".join(f"[{source.source_type}] {source.text}" for source in sources if source.text),
        source_coverage=SourceCoverageSummary(
            source_order=("minutes", "agenda", "packet"),
            statuses=statuses,
            canonical_source_types=tuple(source.source_type for source in sources if source.source_origin == "canonical"),
            fallback_source_types=tuple(source.source_type for source in sources if source.source_origin == "fallback_extract"),
            partial_source_types=tuple(key for key, value in statuses.items() if value == "partial"),
            missing_source_types=tuple(key for key, value in statuses.items() if value == "missing"),
            available_source_types=tuple(key for key, value in statuses.items() if value != "missing"),
            coverage_ratio=0.0,
            coverage_checksum="sha256:test",
        ),
    )


def _compose_source(source_type: str, text: str) -> ComposedSourceDocument:
    return ComposedSourceDocument(
        source_type=source_type,
        source_origin="canonical",
        coverage_status="present",
        text=text,
        canonical_document_id=f"canon-{source_type}",
        revision_id=f"{source_type}-rev-1",
        revision_number=1,
        extraction_status="processed",
        extracted_at="2026-03-06T00:00:00Z",
        span_count=1,
    )
