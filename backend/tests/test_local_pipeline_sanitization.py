from __future__ import annotations

from councilsense.app.local_pipeline import (
    _build_claims_from_findings,
    _derive_grounded_sections,
    _focus_source_text,
    _normalize_action_sentence,
    _normalize_decision_sentence,
    _normalize_generated_text,
)


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
