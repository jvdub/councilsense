from __future__ import annotations

from councilsense.app.local_pipeline import (
    _AuthorityConflictSignal,
    _AuthorityPolicyResult,
    _MeetingMaterialContext,
    _apply_material_context,
    _apply_structured_relevance_carry_through,
    _build_grounded_summary,
    _build_claims_from_findings,
    _deterministic_summarize,
    _derive_grounded_sections,
    _evaluate_authority_policy,
    _focus_source_text,
    _materialize_llm_summary_output,
    _normalize_action_sentence,
    _normalize_decision_sentence,
    _normalize_generated_text,
)
from councilsense.app.multi_document_compose import (
    ComposedSourceDocument,
    ComposedSourceSpan,
    SourceCoverageSummary,
    SummarizeComposeInput,
)
from councilsense.app.summarization import ClaimEvidencePointer, StructuredRelevance, StructuredRelevanceField


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


def test_build_grounded_summary_prefers_outcomes_and_direction_over_motion_boilerplate() -> None:
    source_text = (
        "Management Analyst Terrence Dela Pena presented the Second Quarterly Financial Report, highlighting the City's budget status and capital projects. "
        "City Council provided direction to Staff and GSBS Consulting regarding moving forward on the future land use process. "
        "MOTION: Councilmember Wright moved to adopt an Ordinance of Eagle Mountain City, Utah, Amending the Eagle Mountain Municipal Code Section 2.45 regarding Youth Council with updated revisions made in Work Session. "
        "Councilmember Clark seconded the motion. "
        "The motion passed with a unanimous vote."
    )

    summary = _build_grounded_summary(source_text)

    assert "Youth Council" in summary
    assert "provided direction" in summary
    assert "seconded the motion" not in summary
    assert "The motion passed with a unanimous vote" not in summary


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
            authoritative_locator_precision=None,
            outcome_source_types=("agenda",),
            source_statuses={"minutes": "missing", "agenda": "present", "packet": "missing"},
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


def test_structured_relevance_carry_through_upgrades_generic_action_only_text() -> None:
    summary, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary="The council approved the proposal.",
        key_decisions=("Approved the item.",),
        key_actions=(),
        structured_relevance=_build_structured_relevance_fixture(
            subject="North Gateway rezoning application",
            location="North Gateway District",
            action="approved",
            scale="142 acres and 893 units",
        ),
        authority_policy=_AuthorityPolicyResult(
            authority_outcome="minutes_authoritative",
            publication_status="processed",
            reason_codes=(),
            summarize_text="Council approved the North Gateway rezoning application.",
            authoritative_source_type="minutes",
            authoritative_locator_precision="precise",
            outcome_source_types=("minutes",),
            source_statuses={"minutes": "present", "agenda": "present", "packet": "present"},
            preview_only=False,
            conflicts=(),
        ),
    )

    assert "North Gateway rezoning application" in summary
    assert "North Gateway District" in summary
    assert key_decisions[0] == summary
    assert "Approved the item" not in key_decisions[0]
    assert key_actions == ()


def test_structured_relevance_carry_through_preserves_conflict_uncertainty() -> None:
    summary, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary="Agenda materials for this meeting preview scheduled items rather than confirmed outcomes.",
        key_decisions=(),
        key_actions=(),
        structured_relevance=_build_structured_relevance_fixture(
            subject="Main Street paving contract",
            location="Main Street",
            scale="$1,250,000",
        ),
        authority_policy=_AuthorityPolicyResult(
            authority_outcome="unresolved_conflict",
            publication_status="limited_confidence",
            reason_codes=("missing_authoritative_minutes", "unresolved_source_conflict"),
            summarize_text="[agenda] Consider adoption of Resolution 2026-09 awarding the Main Street paving contract.",
            authoritative_source_type=None,
            authoritative_locator_precision=None,
            outcome_source_types=("agenda", "packet"),
            source_statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
            preview_only=True,
            conflicts=(),
        ),
    )

    assert "Main Street paving contract" in summary
    assert "final action remains uncertain" in summary
    assert "sources conflict" in summary
    assert "No decisions or completed actions are recorded yet" in summary
    assert key_decisions == ()
    assert key_actions == ()


def test_structured_relevance_carry_through_preserves_weak_precision_downgrade() -> None:
    summary, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary="The council approved the permit.",
        key_decisions=("Approved the item.",),
        key_actions=(),
        structured_relevance=_build_structured_relevance_fixture(
            subject="temporary road closure permit",
            location="parade route",
            action="approved",
        ),
        authority_policy=_AuthorityPolicyResult(
            authority_outcome="minutes_authoritative_weak_precision",
            publication_status="limited_confidence",
            reason_codes=("weak_evidence_precision",),
            summarize_text="Council authorized the temporary road closure permit for the parade route.",
            authoritative_source_type="minutes",
            authoritative_locator_precision="weak",
            outcome_source_types=("minutes",),
            source_statuses={"minutes": "present", "agenda": "present", "packet": "missing"},
            preview_only=False,
            conflicts=(),
        ),
    )

    assert "temporary road closure permit" in summary
    assert "parade route" in summary
    assert "evidence locators remain weak" in summary
    assert key_decisions[0] == summary
    assert key_actions == ()


def test_structured_relevance_carry_through_preserves_supplemental_sources_missing_downgrade() -> None:
    summary, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary="The council approved the item.",
        key_decisions=("Approved the item.",),
        key_actions=(),
        structured_relevance=_build_structured_relevance_fixture(
            subject="interfund transfer resolution",
            action="approved",
        ),
        authority_policy=_AuthorityPolicyResult(
            authority_outcome="supplemental_coverage_missing",
            publication_status="limited_confidence",
            reason_codes=("supplemental_sources_missing",),
            summarize_text="Council approved the interfund transfer resolution.",
            authoritative_source_type="minutes",
            authoritative_locator_precision="precise",
            outcome_source_types=("minutes",),
            source_statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
            preview_only=False,
            conflicts=(),
        ),
    )

    assert "interfund transfer resolution" in summary
    assert "supporting agenda or packet materials are missing" in summary
    assert key_decisions[0] == summary
    assert "Approved the item" not in key_decisions[0]
    assert key_actions == ()


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


def test_evaluate_authority_policy_downgrades_when_authoritative_minutes_have_only_weak_locators() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                source_type="minutes",
                text="Council authorized the temporary road closure permit for the parade route.",
                locator_precision="weak",
            ),
            _compose_source(
                source_type="agenda",
                text="Consider parade route road closure permit and traffic control plan.",
            ),
        ),
        statuses={"minutes": "present", "agenda": "present", "packet": "missing"},
    )

    policy = _evaluate_authority_policy(compose_input=compose_input)

    assert policy.authority_outcome == "minutes_authoritative_weak_precision"
    assert policy.publication_status == "limited_confidence"
    assert policy.reason_codes == ("weak_evidence_precision",)
    assert policy.preview_only is False


def test_derive_grounded_sections_excludes_city_name_topics() -> None:
    source_text = (
        "Eagle Mountain City Council approved a motion to adopt the transportation plan. "
        "The Council directed staff to schedule a public hearing for zoning updates. "
        "Residents discussed traffic and infrastructure improvements."
    )

    _, _, notable_topics = _derive_grounded_sections(source_text)

    assert "eagle" not in notable_topics
    assert "mountain" not in notable_topics


def test_derive_grounded_sections_suppresses_appointment_name_and_table_fragments_from_topics() -> None:
    source_text = (
        "The Council scheduled appointment of Marcia Vasquez to the planning commission. "
        "The appointment table listed year term beginning January for the seat."
    )

    _, key_actions, notable_topics = _derive_grounded_sections(source_text)

    assert key_actions
    assert "Board and Commission Appointments" in notable_topics
    lower_topics = {topic.lower() for topic in notable_topics}
    assert "appointment of marcia vasquez" not in lower_topics
    assert "year term" not in lower_topics
    assert "term beginning" not in lower_topics


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
        compose_input=None,
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
        compose_input=None,
        fallback_claim="Fallback claim",
    )

    assert claims
    pointer = claims[0].evidence[0]
    assert pointer.section_ref is not None
    assert ".sentence." in pointer.section_ref
    assert pointer.char_start is not None
    assert pointer.char_end is not None


def test_build_claims_from_findings_attaches_canonical_document_and_span_linkage_with_safe_degradation() -> None:
    claims = _build_claims_from_findings(
        key_decisions=("Motion carried to authorize the temporary road closure permit for the parade route.",),
        key_actions=(),
        source_text="[minutes] Motion carried to authorize the temporary road closure permit for the parade route.",
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=_build_compose_input(
            sources=(
                _compose_source(
                    "minutes",
                    "Motion carried to authorize the temporary road closure permit for the parade route.",
                    locator_precision="weak",
                    spans=(
                        ComposedSourceSpan(
                            span_id="span-minutes-weak",
                            artifact_id="artifact-minutes-weak",
                            stable_section_path="minutes/page/unknown",
                            page_number=None,
                            line_index=None,
                            start_char_offset=None,
                            end_char_offset=None,
                            span_text="Motion carried to authorize the temporary road closure permit for the parade route.",
                        ),
                    ),
                ),
            ),
            statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
        ),
        fallback_claim="Fallback claim",
    )

    pointer = claims[0].evidence[0]
    assert pointer.document_id == "canon-minutes"
    assert pointer.span_id == "span-minutes-weak"
    assert pointer.document_kind == "minutes"
    assert pointer.section_path == "minutes/page/unknown"
    assert pointer.precision == "file"
    assert pointer.confidence == "low"


def test_build_claims_from_findings_attaches_precise_canonical_span_linkage() -> None:
    claims = _build_claims_from_findings(
        key_decisions=("Council adopted ordinance 2026-12.",),
        key_actions=(),
        source_text="[minutes] Council adopted ordinance 2026-12.",
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=_build_compose_input(
            sources=(
                _compose_source(
                    "minutes",
                    "Council adopted ordinance 2026-12.",
                    spans=(
                        ComposedSourceSpan(
                            span_id="span-minutes-precise",
                            artifact_id="artifact-minutes-precise",
                            stable_section_path="minutes/section/2",
                            page_number=6,
                            line_index=3,
                            start_char_offset=42,
                            end_char_offset=76,
                            span_text="Council adopted ordinance 2026-12.",
                        ),
                    ),
                ),
            ),
            statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
        ),
        fallback_claim="Fallback claim",
    )

    pointer = claims[0].evidence[0]
    assert pointer.artifact_id == "artifact-minutes-precise"
    assert pointer.document_id == "canon-minutes"
    assert pointer.span_id == "span-minutes-precise"
    assert pointer.document_kind == "minutes"
    assert pointer.section_path == "minutes/section/2"
    assert pointer.precision == "offset"
    assert pointer.confidence == "high"
    assert pointer.char_start == 42
    assert pointer.char_end == 76


def test_deterministic_summarize_synthesizes_grounded_structured_relevance_from_minutes() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                "Council approved the North Gateway rezoning application for the North Gateway District covering 142 acres and 893 units on March 9.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-minutes-relevance-1",
                        artifact_id="artifact-minutes-relevance-1",
                        stable_section_path="minutes/section/4",
                        page_number=7,
                        line_index=2,
                        start_char_offset=18,
                        end_char_offset=138,
                        span_text="Council approved the North Gateway rezoning application for the North Gateway District covering 142 acres and 893 units on March 9.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert output.structured_relevance is not None
    assert output.structured_relevance.subject is not None
    assert output.structured_relevance.location is not None
    assert output.structured_relevance.action is not None
    assert output.structured_relevance.scale is not None
    assert output.structured_relevance.subject.value == "North Gateway rezoning application"
    assert output.structured_relevance.location.value == "North Gateway District"
    assert output.structured_relevance.action.value == "approved"
    assert output.structured_relevance.scale.value == "142 acres and 893 units"
    assert tuple(tag.tag for tag in output.structured_relevance.impact_tags) == ("housing", "land_use")
    assert tuple(tag.tag for tag in output.structured_relevance.items[0].impact_tags) == ("housing", "land_use")
    assert output.summary == output.key_decisions[0]
    assert "proposal" not in output.summary.lower()
    assert "North Gateway rezoning application" in output.summary
    assert "North Gateway District" in output.summary
    assert output.structured_relevance.items[0].subject is not None
    assert output.structured_relevance.items[0].subject.evidence[0].section_ref == "minutes.section.4"
    assert output.structured_relevance.items[0].subject.evidence[0].artifact_id == "artifact-minutes-relevance-1"
    assert output.structured_relevance.items[0].impact_tags[0].evidence[0].section_ref == "minutes.section.4"


def test_deterministic_summarize_degrades_safely_for_preview_only_partial_bundle() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "agenda",
                "Consider adoption of Resolution 2026-09 awarding the Main Street paving contract on Main Street for $1,250,000.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-agenda-relevance-1",
                        artifact_id="artifact-agenda-relevance-1",
                        stable_section_path="agenda/section/7",
                        page_number=None,
                        line_index=None,
                        start_char_offset=None,
                        end_char_offset=None,
                        span_text="Consider adoption of Resolution 2026-09 awarding the Main Street paving contract on Main Street for $1,250,000.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "missing", "agenda": "present", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="agenda",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="same_day_or_future",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert output.structured_relevance is not None
    assert output.structured_relevance.subject is not None
    assert output.structured_relevance.subject.value == "Main Street paving contract"
    assert output.structured_relevance.location is not None
    assert output.structured_relevance.location.value == "Main Street"
    assert output.structured_relevance.scale is not None
    assert output.structured_relevance.scale.value == "$1,250,000"
    assert output.structured_relevance.action is None
    assert output.structured_relevance.subject.confidence == "medium"
    assert output.structured_relevance.location.confidence == "medium"
    assert output.structured_relevance.scale.confidence == "medium"
    assert tuple(tag.tag for tag in output.structured_relevance.impact_tags) == ("traffic",)
    assert output.structured_relevance.impact_tags[0].confidence == "medium"
    assert "preview scheduled items rather than confirmed outcomes" in output.summary
    assert "Main Street paving contract on Main Street for $1,250,000" in output.summary
    assert "No decisions or completed actions are recorded yet" in output.summary


def test_deterministic_summarize_preserves_conflict_uncertainty_with_specific_subject_and_location() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "agenda",
                "Consider adoption of Resolution 2026-09 awarding the Main Street paving contract on Main Street for $1,250,000.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-agenda-relevance-conflict-1",
                        artifact_id="artifact-agenda-relevance-conflict-1",
                        stable_section_path="agenda/section/7",
                        page_number=None,
                        line_index=None,
                        start_char_offset=None,
                        end_char_offset=None,
                        span_text="Consider adoption of Resolution 2026-09 awarding the Main Street paving contract on Main Street for $1,250,000.",
                    ),
                ),
            ),
            _compose_source(
                "packet",
                "Staff recommendation was to continue Resolution 2026-09 pending updated bids for the Main Street paving contract on Main Street.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-packet-relevance-conflict-1",
                        artifact_id="artifact-packet-relevance-conflict-1",
                        stable_section_path="packet/section/3",
                        page_number=None,
                        line_index=None,
                        start_char_offset=None,
                        end_char_offset=None,
                        span_text="Staff recommendation was to continue Resolution 2026-09 pending updated bids for the Main Street paving contract on Main Street.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="agenda",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="same_day_or_future",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert authority_policy.authority_outcome == "unresolved_conflict"
    assert authority_policy.publication_status == "limited_confidence"
    assert output.structured_relevance is not None
    assert output.structured_relevance.subject is not None
    assert output.structured_relevance.subject.value == "Main Street paving contract"
    assert output.structured_relevance.subject.confidence == "medium"
    assert output.structured_relevance.location is not None
    assert output.structured_relevance.location.value == "Main Street"
    assert output.structured_relevance.location.confidence == "medium"
    assert output.structured_relevance.action is None
    assert tuple(tag.tag for tag in output.structured_relevance.impact_tags) == ("traffic",)
    assert output.structured_relevance.impact_tags[0].confidence == "medium"
    assert "preview scheduled items rather than confirmed outcomes" in output.summary
    assert "No decisions or completed actions are recorded yet" in output.summary
    assert "approved the Main Street paving contract" not in output.summary


def test_deterministic_summarize_marks_fallback_extract_specificity_as_low_confidence() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "agenda",
                "Agenda scheduled the River Road Corridor Plan for River Road.",
                locator_precision="unknown",
                source_origin="fallback_extract",
            ),
        ),
        statuses={"minutes": "missing", "agenda": "present", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="agenda",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="same_day_or_future",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert authority_policy.publication_status == "limited_confidence"
    assert output.structured_relevance is not None
    assert output.structured_relevance.subject is not None
    assert output.structured_relevance.subject.value == "River Road Corridor Plan"
    assert output.structured_relevance.subject.confidence == "low"
    assert output.structured_relevance.location is not None
    assert output.structured_relevance.location.value == "River Road Corridor"
    assert output.structured_relevance.location.confidence == "low"
    assert output.structured_relevance.action is not None
    assert output.structured_relevance.action.confidence == "low"
    assert "preview scheduled consideration of the River Road Corridor Plan" in output.summary
    assert "published minutes are not available" in output.summary


def test_deterministic_summarize_classifies_utilities_fees_and_parks_from_grounded_snippets() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                (
                    "Council adopted the stormwater utility fee schedule for fiscal year 2027. "
                    "Council approved the Silver Lake Park playground renovation."
                ),
                spans=(
                    ComposedSourceSpan(
                        span_id="span-minutes-impact-1",
                        artifact_id="artifact-minutes-impact-1",
                        stable_section_path="minutes/section/8",
                        page_number=11,
                        line_index=3,
                        start_char_offset=12,
                        end_char_offset=78,
                        span_text="Council adopted the stormwater utility fee schedule for fiscal year 2027.",
                    ),
                    ComposedSourceSpan(
                        span_id="span-minutes-impact-2",
                        artifact_id="artifact-minutes-impact-2",
                        stable_section_path="minutes/section/9",
                        page_number=12,
                        line_index=1,
                        start_char_offset=80,
                        end_char_offset=138,
                        span_text="Council approved the Silver Lake Park playground renovation.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )
    rerun = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert output.structured_relevance is not None
    assert rerun.structured_relevance is not None
    assert tuple(tag.tag for tag in output.structured_relevance.impact_tags) == ("utilities", "parks", "fees")
    assert output.structured_relevance.to_payload() == rerun.structured_relevance.to_payload()
    assert tuple(tag.tag for tag in output.structured_relevance.items[0].impact_tags) == ("utilities", "fees")
    assert tuple(tag.tag for tag in output.structured_relevance.items[1].impact_tags) == ("parks",)
    assert output.structured_relevance.items[0].impact_tags[0].evidence[0].artifact_id == "artifact-minutes-impact-1"
    assert output.structured_relevance.items[1].impact_tags[0].evidence[0].artifact_id == "artifact-minutes-impact-2"


def test_deterministic_summarize_omits_impact_tags_without_explicit_support_beyond_location_tokens() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                "Council approved Resolution 2026-10 for the annual report on Main Street.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-minutes-impact-3",
                        artifact_id="artifact-minutes-impact-3",
                        stable_section_path="minutes/section/10",
                        page_number=13,
                        line_index=2,
                        start_char_offset=15,
                        end_char_offset=84,
                        span_text="Council approved Resolution 2026-10 for the annual report on Main Street.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert output.structured_relevance is not None
    assert output.structured_relevance.location is not None
    assert output.structured_relevance.location.value == "Main Street"
    assert output.structured_relevance.impact_tags == ()
    assert output.structured_relevance.items[0].impact_tags == ()


def test_deterministic_summarize_structured_relevance_is_stable_across_repeated_runs() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                "Council approved the Old Airport Road right-of-way acquisition covering 12 acres and a 3-1 vote.",
                spans=(
                    ComposedSourceSpan(
                        span_id="span-minutes-relevance-2",
                        artifact_id="artifact-minutes-relevance-2",
                        stable_section_path="minutes/section/6",
                        page_number=9,
                        line_index=4,
                        start_char_offset=22,
                        end_char_offset=111,
                        span_text="Council approved the Old Airport Road right-of-way acquisition covering 12 acres and a 3-1 vote.",
                    ),
                ),
            ),
        ),
        statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    first = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )
    second = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-03-09",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert first.structured_relevance is not None
    assert second.structured_relevance is not None
    assert first.structured_relevance.to_payload() == second.structured_relevance.to_payload()
    assert tuple(tag.tag for tag in first.structured_relevance.impact_tags) == ("traffic",)


def test_deterministic_summary_extracts_structured_relevance_from_coarse_minutes_span() -> None:
    span_text = (
        "Management Analyst Terrence Dela Pena presented the Second Quarterly Financial Report, highlighting the City's budget status and capital projects. "
        "Brandon Larsen, Planning Director, and GSBS Consulting reviewed the future land use process and land use designations. "
        "City Council provided direction to Staff and GSBS Consulting regarding moving forward. "
        "Assistant to the City Manager Natalie Winterton presented a proposed ordinance updating the Youth Council Code. "
        "MOTION: Councilmember Wright moved to adopt an Ordinance of Eagle Mountain City, Utah, Amending the Eagle Mountain Municipal Code Section 2.45 regarding Youth Council with updated revisions made in Work Session. "
        "Councilmember Clark seconded the motion. The motion passed with a unanimous vote."
    )
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                span_text,
                spans=(
                    ComposedSourceSpan(
                        span_id="span-minutes-coarse",
                        artifact_id="artifact-minutes-coarse",
                        stable_section_path="minutes/content/1",
                        page_number=None,
                        line_index=0,
                        start_char_offset=None,
                        end_char_offset=None,
                        span_text=span_text,
                    ),
                ),
            ),
            _compose_source("agenda", "Agenda includes future land use discussion and Youth Council ordinance review."),
            _compose_source("packet", "Packet includes staff background for future land use planning and Youth Council code revisions."),
        ),
        statuses={"minutes": "present", "agenda": "present", "packet": "present"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _deterministic_summarize(
        text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-02-03",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    assert output.summary
    assert "Youth Council" in output.summary
    assert "seconded the motion" not in output.summary
    assert output.structured_relevance is not None
    assert output.structured_relevance.subject is not None
    assert "Youth Council" in output.structured_relevance.subject.value


def test_materialize_llm_summary_output_supplements_notable_topics_from_summary_text() -> None:
    compose_input = _build_compose_input(
        sources=(
            _compose_source(
                "minutes",
                "The Council received a legislative update, reviewed the quarterly financial report, gave direction on future land use designations, and updated the Youth Council code.",
            ),
            _compose_source("agenda", "Agenda includes legislative update, quarterly financial report, and Youth Council code discussion."),
            _compose_source("packet", "Packet includes future land use maps and Youth Council code revisions."),
        ),
        statuses={"minutes": "present", "agenda": "present", "packet": "present"},
    )
    authority_policy = _evaluate_authority_policy(compose_input=compose_input)

    output = _materialize_llm_summary_output(
        response_text=(
            '{"summary":"The Eagle Mountain City Council received a legislative update and reviewed the Second Quarterly Financial Report. '
            'The Council provided direction on future land use designations and recommended corrections to the Youth Council municipal code.",'
            '"claim":"The Council recommended corrections to the Youth Council municipal code."}'
        ),
        source_text=authority_policy.summarize_text,
        artifact_id="artifact-local:test.txt",
        section_ref="compose.multi_document",
        compose_input=compose_input,
        material_context=_MeetingMaterialContext(
            document_kind="minutes",
            meeting_date_iso="2026-02-03",
            meeting_temporal_status="completed",
        ),
        authority_policy=authority_policy,
        topic_hardening_enabled=True,
        specificity_retention_enabled=True,
        evidence_projection_enabled=True,
    )

    lower_topics = {topic.lower() for topic in output.notable_topics}
    assert "legislative update" in lower_topics
    assert "quarterly financial report" in lower_topics or "budget and fiscal planning" in lower_topics
    assert "land use planning" in lower_topics
    assert "youth council code" in lower_topics


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


def _build_structured_relevance_fixture(
    *,
    subject: str | None = None,
    location: str | None = None,
    action: str | None = None,
    scale: str | None = None,
) -> StructuredRelevance:
    evidence = ClaimEvidencePointer(
        artifact_id="artifact-test",
        section_ref="minutes.section.1",
        char_start=None,
        char_end=None,
        excerpt="Grounded evidence excerpt.",
        confidence="high",
    )

    def make_field(value: str | None) -> StructuredRelevanceField | None:
        if value is None:
            return None
        return StructuredRelevanceField(value=value, evidence=(evidence,), confidence="high")

    return StructuredRelevance(
        subject=make_field(subject),
        location=make_field(location),
        action=make_field(action),
        scale=make_field(scale),
        impact_tags=(),
        items=(),
    )


def _compose_source(
    source_type: str,
    text: str,
    locator_precision: str = "precise",
    spans: tuple[ComposedSourceSpan, ...] = (),
    source_origin: str = "canonical",
) -> ComposedSourceDocument:
    return ComposedSourceDocument(
        source_type=source_type,
        source_origin=source_origin,
        coverage_status="present",
        text=text,
        locator_precision=locator_precision,
        canonical_document_id=f"canon-{source_type}",
        revision_id=f"{source_type}-rev-1",
        revision_number=1,
        extraction_status="processed",
        extracted_at="2026-03-06T00:00:00Z",
        span_count=len(spans),
        spans=spans,
    )
