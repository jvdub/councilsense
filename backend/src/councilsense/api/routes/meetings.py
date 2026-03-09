from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.api.profile import UserProfileService
from councilsense.app.settings import MeetingDetailAdditiveApiSettings
from councilsense.app.settings import MeetingDetailFollowUpPromptsApiSettings
from councilsense.app.settings import MeetingDetailResidentRelevanceApiSettings
from councilsense.app.settings import Settings
from councilsense.db import InvalidMeetingListCursorError, MeetingListCursor, MeetingReadRepository
from councilsense.db.meetings import MeetingDetail
from councilsense.db.meetings import MeetingDetailClaim
from councilsense.db.meetings import MeetingDetailEvidencePointer


router = APIRouter(prefix="/v1", tags=["meetings"])


CITY_ACCESS_DENIED_BODY = {
    "error": {
        "code": "forbidden",
        "message": "City access denied",
    }
}


class MeetingListItemResponse(BaseModel):
    id: str
    city_id: str
    city_name: str | None
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    meeting_date: str | None
    body_name: str | None
    status: str | None
    confidence_label: str | None
    reader_low_confidence: bool


class CityMeetingsListResponse(BaseModel):
    items: list[MeetingListItemResponse]
    next_cursor: str | None
    limit: int


class MeetingEvidencePointerResponse(BaseModel):
    id: str
    artifact_id: str
    source_document_url: str | None
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str
    document_id: str | None = Field(default=None, exclude=True)
    span_id: str | None = Field(default=None, exclude=True)
    document_kind: str | None = Field(default=None, exclude=True)
    section_path: str | None = Field(default=None, exclude=True)
    precision: str | None = Field(default=None, exclude=True)
    confidence: str | None = Field(default=None, exclude=True)


class MeetingEvidenceReferenceV2Response(BaseModel):
    evidence_id: str
    document_id: str | None
    artifact_id: str
    document_kind: str
    section_path: str
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None
    char_end: int | None
    precision: str
    confidence: str | None
    excerpt: str


class MeetingClaimResponse(BaseModel):
    id: str
    claim_order: int
    claim_text: str
    evidence: list[MeetingEvidencePointerResponse]


class MeetingDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    city_id: str
    city_name: str | None
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    meeting_date: str | None
    body_name: str | None
    source_document_kind: str | None
    source_document_url: str | None
    status: str | None
    confidence_label: str | None
    reader_low_confidence: bool
    publication_id: str | None
    published_at: str | None
    summary: str | None
    key_decisions: list[str]
    key_actions: list[str]
    notable_topics: list[str]
    evidence_references_v2: list[MeetingEvidenceReferenceV2Response]
    evidence_references: list[str]
    claims: list[MeetingClaimResponse]


def _serialize_evidence_reference(evidence: MeetingEvidencePointerResponse) -> str:
    section = evidence.section_ref if evidence.section_ref is not None else "no-section"
    char_start = str(evidence.char_start) if evidence.char_start is not None else "?"
    char_end = str(evidence.char_end) if evidence.char_end is not None else "?"
    return f"{evidence.excerpt} | {evidence.artifact_id}#{section}:{char_start}-{char_end}"


def _normalize_reference_text(value: str) -> str:
    return " ".join(value.lower().split())


def _is_file_level_section(section_ref: str | None) -> bool:
    return (section_ref or "").strip().lower() in {"", "artifact.html", "artifact.pdf", "meeting.metadata"}


_PRECISION_RANKS = {
    "offset": 0,
    "span": 1,
    "section": 2,
    "file": 3,
}
_ADDITIVE_BLOCK_FIELD_NAMES = ("planned", "outcomes", "planned_outcome_mismatches")
_RESIDENT_RELEVANCE_FIELD_NAMES = ("subject", "location", "action", "scale")
_RESIDENT_RELEVANCE_IMPACT_TAG_ORDER = {
    "housing": 0,
    "traffic": 1,
    "utilities": 2,
    "parks": 3,
    "fees": 4,
    "land_use": 5,
}
_FOLLOW_UP_PROMPT_ORDER = (
    ("project_identity", "What project or item is this about?"),
    ("location", "Where does this apply?"),
    ("disposition", "What happened at this meeting?"),
    ("scale", "How large is it?"),
    ("timeline", "What is the timeline?"),
    ("next_step", "What happens next?"),
)
_TEMPORAL_KEYWORDS = (
    "today",
    "tomorrow",
    "tonight",
    "next week",
    "next month",
    "next year",
    "this week",
    "this month",
    "this year",
    "deadline",
    "schedule",
    "scheduled",
    "timeline",
    "by ",
    "within ",
    "through ",
    "before ",
    "after ",
    "starting ",
    "beginning ",
    "ending ",
)
_INTERNAL_ONLY_KEY_ACTION_PATTERNS = (
    "operator",
    "workflow",
    "queue",
    "retry",
    "replay",
    "triage",
    "audit",
    "backfill",
    "telemetry",
    "instrumentation",
)


class MeetingSuggestedPromptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(description="Stable prompt identifier from the bounded ST-035 prompt set.")
    prompt: str = Field(description="Exact frozen prompt text for the prompt identifier.")
    answer: str = Field(description="Single-sentence grounded answer for the prompt.")
    evidence_references_v2: list[MeetingEvidenceReferenceV2Response] = Field(
        description="One or more evidence-v2 references that substantiate the emitted answer text."
    )


_EVIDENCE_REFERENCE_V2_REQUIRED_STRING_FIELDS = (
    "evidence_id",
    "artifact_id",
    "document_kind",
    "section_path",
    "precision",
    "excerpt",
)


def _stable_section_locator(evidence: MeetingEvidencePointerResponse) -> str:
    value = evidence.section_path or evidence.section_ref or ""
    return value.strip().lower()


def _precision_rank(evidence: MeetingEvidencePointerResponse) -> int:
    if evidence.precision in _PRECISION_RANKS:
        return _PRECISION_RANKS[evidence.precision]

    has_offsets = evidence.char_start is not None and evidence.char_end is not None
    if has_offsets:
        return 0
    if not _is_file_level_section(evidence.section_ref):
        return 2
    return 3


def _equivalence_key(evidence: MeetingEvidencePointerResponse) -> tuple[str, str]:
    return (evidence.artifact_id, _normalize_reference_text(evidence.excerpt))


def _supports_v2_projection(evidence: MeetingEvidencePointerResponse) -> bool:
    return all(
        value is not None and value.strip()
        for value in (evidence.document_kind, evidence.section_path, evidence.precision)
    )


def _metadata_completeness_score(evidence: MeetingEvidencePointerResponse) -> int:
    score = 0
    for value in (
        evidence.document_id,
        evidence.span_id,
        evidence.document_kind,
        evidence.section_path,
        evidence.precision,
        evidence.confidence,
    ):
        if value is not None and value.strip():
            score += 1
    return score


def _evidence_preference_key(evidence: MeetingEvidencePointerResponse) -> tuple[int, int, int, str, int, int, str]:
    return (
        _precision_rank(evidence),
        0 if _supports_v2_projection(evidence) else 1,
        -_metadata_completeness_score(evidence),
        _stable_section_locator(evidence),
        evidence.char_start if evidence.char_start is not None else 10**9,
        evidence.char_end if evidence.char_end is not None else 10**9,
        evidence.id,
    )


def _prefer_evidence_pointer(
    *,
    current: MeetingEvidencePointerResponse,
    challenger: MeetingEvidencePointerResponse,
) -> MeetingEvidencePointerResponse:
    if _evidence_preference_key(challenger) < _evidence_preference_key(current):
        return challenger
    return current


def _evidence_order_key(evidence: MeetingEvidencePointerResponse) -> tuple[int, str, str, str, int, int, str]:
    return (
        _precision_rank(evidence),
        (evidence.document_kind or "").strip().lower(),
        evidence.artifact_id,
        _stable_section_locator(evidence),
        evidence.char_start if evidence.char_start is not None else 10**9,
        evidence.char_end if evidence.char_end is not None else 10**9,
        _normalize_reference_text(evidence.excerpt),
    )


def _build_evidence_references(claims: list[MeetingClaimResponse]) -> list[str]:
    deduped_references: dict[tuple[str, str], MeetingEvidencePointerResponse] = {}
    for claim in claims:
        for evidence in claim.evidence:
            key = _equivalence_key(evidence)
            seen = deduped_references.get(key)
            if seen is None:
                deduped_references[key] = evidence
                continue

            deduped_references[key] = _prefer_evidence_pointer(current=seen, challenger=evidence)

    ordered = sorted(deduped_references.values(), key=_evidence_order_key)
    return [_serialize_evidence_reference(evidence) for evidence in ordered]


def _build_evidence_references_v2(claims: list[MeetingClaimResponse]) -> list[MeetingEvidenceReferenceV2Response]:
    deduped_references: dict[tuple[str, str], MeetingEvidencePointerResponse] = {}
    for claim in claims:
        for evidence in claim.evidence:
            key = _equivalence_key(evidence)
            seen = deduped_references.get(key)
            if seen is None:
                deduped_references[key] = evidence
                continue

            deduped_references[key] = _prefer_evidence_pointer(current=seen, challenger=evidence)

    ordered = sorted(
        (evidence for evidence in deduped_references.values() if _supports_v2_projection(evidence)),
        key=_evidence_order_key,
    )
    return [
        MeetingEvidenceReferenceV2Response(
            evidence_id=evidence.id,
            document_id=evidence.document_id,
            artifact_id=evidence.artifact_id,
            document_kind=evidence.document_kind or "",
            section_path=evidence.section_path or "",
            char_start=evidence.char_start,
            char_end=evidence.char_end,
            precision=evidence.precision or "",
            confidence=evidence.confidence,
            excerpt=evidence.excerpt,
        )
        for evidence in ordered
    ]


def _normalize_evidence_reference_v2_value(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    normalized: dict[str, Any] = {}
    for field_name in _EVIDENCE_REFERENCE_V2_REQUIRED_STRING_FIELDS:
        raw_value = value.get(field_name)
        if not isinstance(raw_value, str):
            return None
        stripped = raw_value.strip()
        if not stripped:
            return None
        normalized[field_name] = stripped

    for field_name in ("document_id", "confidence"):
        raw_value = value.get(field_name)
        if raw_value is None:
            normalized[field_name] = None
            continue
        if not isinstance(raw_value, str):
            return None
        stripped = raw_value.strip()
        normalized[field_name] = stripped or None

    for field_name in ("page_start", "page_end", "char_start", "char_end"):
        raw_value = value.get(field_name)
        if raw_value is None:
            normalized[field_name] = None
            continue
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            return None
        normalized[field_name] = raw_value

    return normalized


def _additive_evidence_v2_order_key(reference: Mapping[str, Any]) -> tuple[int, str, str, str, int, int, str, str]:
    precision = str(reference["precision"])
    return (
        _PRECISION_RANKS.get(precision, 10**9),
        str(reference["document_kind"]).strip().lower(),
        str(reference["artifact_id"]),
        str(reference["section_path"]),
        reference["char_start"] if reference["char_start"] is not None else 10**9,
        reference["char_end"] if reference["char_end"] is not None else 10**9,
        _normalize_reference_text(str(reference["excerpt"])),
        str(reference["evidence_id"]),
    )


def _normalize_additive_evidence_references_v2(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None

    normalized = [
        reference
        for item in value
        if (reference := _normalize_evidence_reference_v2_value(item)) is not None
    ]
    if normalized or not value:
        return sorted(normalized, key=_additive_evidence_v2_order_key)
    return None


def _normalize_sentence_text(value: str) -> str:
    return " ".join(value.strip().lower().rstrip(".?!;").split())


def _normalize_output_sentence(value: str) -> str:
    normalized = " ".join(value.split()).strip().rstrip(".?!;")
    if not normalized:
        return ""
    return f"{normalized}."


def _normalize_prompt_field_with_evidence(value: object) -> dict[str, Any] | None:
    normalized = _normalize_resident_relevance_field(value)
    if normalized is None:
        return None
    if not normalized.get("evidence_references_v2"):
        return None
    return normalized


def _meeting_evidence_pointer_to_v2(evidence: MeetingDetailEvidencePointer) -> MeetingEvidenceReferenceV2Response | None:
    if not _supports_v2_projection(
        MeetingEvidencePointerResponse(
            id=evidence.id,
            artifact_id=evidence.artifact_id,
            source_document_url=evidence.source_document_url,
            section_ref=evidence.section_ref,
            char_start=evidence.char_start,
            char_end=evidence.char_end,
            excerpt=evidence.excerpt,
            document_id=evidence.document_id,
            span_id=evidence.span_id,
            document_kind=evidence.document_kind,
            section_path=evidence.section_path,
            precision=evidence.precision,
            confidence=evidence.confidence,
        )
    ):
        return None

    return MeetingEvidenceReferenceV2Response(
        evidence_id=evidence.id,
        document_id=evidence.document_id,
        artifact_id=evidence.artifact_id,
        document_kind=evidence.document_kind or "",
        section_path=evidence.section_path or "",
        char_start=evidence.char_start,
        char_end=evidence.char_end,
        precision=evidence.precision or "",
        confidence=evidence.confidence,
        excerpt=evidence.excerpt,
    )


def _dedupe_and_sort_prompt_evidence(
    *reference_groups: list[MeetingEvidenceReferenceV2Response],
) -> list[MeetingEvidenceReferenceV2Response]:
    deduped: dict[tuple[str, str], MeetingEvidenceReferenceV2Response] = {}
    for group in reference_groups:
        for reference in group:
            key = (reference.artifact_id, _normalize_reference_text(reference.excerpt))
            seen = deduped.get(key)
            if seen is None or _additive_evidence_v2_order_key(reference.model_dump()) < _additive_evidence_v2_order_key(
                seen.model_dump()
            ):
                deduped[key] = reference
    return sorted(deduped.values(), key=lambda item: _additive_evidence_v2_order_key(item.model_dump()))


def _claim_evidence_v2(claim: MeetingDetailClaim) -> list[MeetingEvidenceReferenceV2Response]:
    references = [
        reference
        for evidence in claim.evidence
        if (reference := _meeting_evidence_pointer_to_v2(evidence)) is not None
    ]
    return _dedupe_and_sort_prompt_evidence(references)


def _find_grounded_claim_for_action(
    *,
    key_action: str,
    claims: tuple[MeetingDetailClaim, ...],
) -> tuple[MeetingDetailClaim, list[MeetingEvidenceReferenceV2Response]] | None:
    normalized_action = _normalize_sentence_text(key_action)
    if not normalized_action:
        return None

    for claim in claims:
        claim_references = _claim_evidence_v2(claim)
        if not claim_references:
            continue

        if _normalize_sentence_text(claim.claim_text) == normalized_action:
            return claim, claim_references

        for reference in claim_references:
            if _normalize_sentence_text(reference.excerpt) == normalized_action:
                return claim, claim_references

    return None


def _looks_like_magnitude_scale(value: str) -> bool:
    normalized = value.lower()
    magnitude_patterns = (
        r"\$\s*\d",
        r"\b\d+[\d,]*\s+(acres?|acreage|units?|homes?|dollars?|million|billion|square feet|sq\.?\s*ft\.?|miles?)\b",
        r"\b\d{1,2}\s*-\s*\d{1,2}\b",
    )
    return any(__import__("re").search(pattern, normalized) for pattern in magnitude_patterns)


def _looks_like_temporal_scale(value: str) -> bool:
    normalized = value.lower()
    if any(keyword in normalized for keyword in _TEMPORAL_KEYWORDS):
        return True

    temporal_patterns = (
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\bq[1-4]\s+\d{4}\b",
        r"\b(?:within|in|for|over)\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)\b",
        r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    )
    return any(__import__("re").search(pattern, normalized) for pattern in temporal_patterns)


def _extract_timeline_phrase_from_text(*, text: str, meeting_date: str | None) -> str | None:
    import re

    normalized = " ".join(text.split()).strip()
    if not normalized:
        return None

    candidates = (
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\bq[1-4]\s+\d{4}\b",
        r"\bnext\s+(?:week|month|year)\b",
        r"\bthis\s+(?:week|month|year)\b",
        r"\bwithin\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)\b",
        r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\bby\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b",
    )
    for pattern in candidates:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match is None:
            continue
        phrase = " ".join(match.group(0).split())
        if meeting_date is not None and phrase == meeting_date:
            continue
        return phrase
    return None


def _is_resident_facing_future_oriented_key_action(value: str) -> bool:
    normalized = _normalize_sentence_text(value)
    if not normalized:
        return False
    if any(pattern in normalized for pattern in _INTERNAL_ONLY_KEY_ACTION_PATTERNS):
        return False
    future_markers = (
        " will ",
        " to publish",
        " to return",
        " to issue",
        " to schedule",
        " to release",
        " to provide",
        " to finalize",
        " to prepare",
    )
    if any(marker in f" {normalized} " for marker in future_markers):
        return True
    return normalized.startswith(("staff to ", "planning ", "city manager to ", "public works to "))


def _build_follow_up_prompt_payload(
    *,
    prompt_id: str,
    prompt: str,
    answer: str,
    evidence_references_v2: list[MeetingEvidenceReferenceV2Response],
) -> dict[str, Any] | None:
    normalized_answer = _normalize_output_sentence(answer)
    if not normalized_answer or not evidence_references_v2:
        return None
    return MeetingSuggestedPromptResponse(
        prompt_id=prompt_id,
        prompt=prompt,
        answer=normalized_answer,
        evidence_references_v2=evidence_references_v2,
    ).model_dump()


def _build_follow_up_prompt_suggestions(detail: MeetingDetail) -> list[dict[str, Any]]:
    normalized_relevance = _normalize_resident_relevance_mapping(detail.structured_relevance)
    if normalized_relevance is None:
        return []

    subject = _normalize_prompt_field_with_evidence(normalized_relevance.get("subject"))
    location = _normalize_prompt_field_with_evidence(normalized_relevance.get("location"))
    action = _normalize_prompt_field_with_evidence(normalized_relevance.get("action"))
    scale = _normalize_prompt_field_with_evidence(normalized_relevance.get("scale"))

    subject_refs = [MeetingEvidenceReferenceV2Response(**reference) for reference in subject.get("evidence_references_v2", [])] if subject else []
    location_refs = [MeetingEvidenceReferenceV2Response(**reference) for reference in location.get("evidence_references_v2", [])] if location else []
    action_refs = [MeetingEvidenceReferenceV2Response(**reference) for reference in action.get("evidence_references_v2", [])] if action else []
    scale_refs = [MeetingEvidenceReferenceV2Response(**reference) for reference in scale.get("evidence_references_v2", [])] if scale else []

    selected_future_action: tuple[str, list[MeetingEvidenceReferenceV2Response]] | None = None
    selected_timeline_action: tuple[str, str, list[MeetingEvidenceReferenceV2Response]] | None = None
    for key_action in detail.key_actions:
        grounded_claim = _find_grounded_claim_for_action(key_action=key_action, claims=detail.claims)
        if grounded_claim is None:
            continue
        if not _is_resident_facing_future_oriented_key_action(key_action):
            continue
        _, claim_references = grounded_claim
        if selected_future_action is None:
            selected_future_action = (key_action, claim_references)
        timeline_phrase = _extract_timeline_phrase_from_text(text=key_action, meeting_date=detail.meeting_date)
        if timeline_phrase is not None and selected_timeline_action is None:
            selected_timeline_action = (key_action, timeline_phrase, claim_references)
        if selected_future_action is not None and selected_timeline_action is not None:
            break

    prompt_entries: dict[str, dict[str, Any]] = {}

    if subject is not None:
        entry = _build_follow_up_prompt_payload(
            prompt_id="project_identity",
            prompt="What project or item is this about?",
            answer=str(subject["value"]),
            evidence_references_v2=subject_refs,
        )
        if entry is not None:
            prompt_entries["project_identity"] = entry

    if location is not None:
        entry = _build_follow_up_prompt_payload(
            prompt_id="location",
            prompt="Where does this apply?",
            answer=f"It applies to {location['value']}",
            evidence_references_v2=location_refs,
        )
        if entry is not None:
            prompt_entries["location"] = entry

    if subject is not None and action is not None:
        entry = _build_follow_up_prompt_payload(
            prompt_id="disposition",
            prompt="What happened at this meeting?",
            answer=f"{subject['value']} was {action['value']}",
            evidence_references_v2=_dedupe_and_sort_prompt_evidence(subject_refs, action_refs),
        )
        if entry is not None:
            prompt_entries["disposition"] = entry

    if scale is not None:
        scale_value = str(scale["value"])
        is_magnitude = _looks_like_magnitude_scale(scale_value)
        is_temporal = _looks_like_temporal_scale(scale_value)
        if is_magnitude:
            entry = _build_follow_up_prompt_payload(
                prompt_id="scale",
                prompt="How large is it?",
                answer=f"The scale in the record is {scale_value}",
                evidence_references_v2=scale_refs,
            )
            if entry is not None:
                prompt_entries["scale"] = entry
        if is_temporal and not is_magnitude:
            entry = _build_follow_up_prompt_payload(
                prompt_id="timeline",
                prompt="What is the timeline?",
                answer=f"The timeline in the record is {scale_value}",
                evidence_references_v2=scale_refs,
            )
            if entry is not None:
                prompt_entries["timeline"] = entry

    if "timeline" not in prompt_entries and selected_timeline_action is not None:
        _, timeline_phrase, claim_references = selected_timeline_action
        entry = _build_follow_up_prompt_payload(
            prompt_id="timeline",
            prompt="What is the timeline?",
            answer=f"The timeline in the record is {timeline_phrase}",
            evidence_references_v2=claim_references,
        )
        if entry is not None:
            prompt_entries["timeline"] = entry

    if selected_future_action is not None:
        key_action_text, claim_references = selected_future_action
        entry = _build_follow_up_prompt_payload(
            prompt_id="next_step",
            prompt="What happens next?",
            answer=key_action_text,
            evidence_references_v2=claim_references,
        )
        if entry is not None:
            prompt_entries["next_step"] = entry

    return [
        prompt_entries[prompt_id]
        for prompt_id, _ in _FOLLOW_UP_PROMPT_ORDER
        if prompt_id in prompt_entries
    ]


def _merge_follow_up_prompt_suggestions(
    *,
    payload: dict[str, Any],
    detail: MeetingDetail,
    follow_up_prompts_api_settings: MeetingDetailFollowUpPromptsApiSettings,
) -> dict[str, Any]:
    sanitized_payload = dict(payload)
    sanitized_payload.pop("suggested_prompts", None)
    if not follow_up_prompts_api_settings.enabled:
        return sanitized_payload

    suggested_prompts = _build_follow_up_prompt_suggestions(detail)
    if suggested_prompts:
        sanitized_payload["suggested_prompts"] = suggested_prompts
    return sanitized_payload


def _normalize_additive_item(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    normalized_item = {key: item_value for key, item_value in value.items() if key != "evidence_references_v2"}
    if "evidence_references_v2" not in value:
        return normalized_item

    normalized_evidence = _normalize_additive_evidence_references_v2(value.get("evidence_references_v2"))
    if normalized_evidence is not None:
        normalized_item["evidence_references_v2"] = normalized_evidence
    return normalized_item


def _normalize_additive_block(*, block_name: str, block_value: object) -> dict[str, Any] | None:
    if not isinstance(block_value, Mapping):
        return None

    raw_items = block_value.get("items")
    if not isinstance(raw_items, list):
        return None

    normalized_block = {key: value for key, value in block_value.items() if key != "items"}
    normalized_block["items"] = [
        item
        for raw_item in raw_items
        if (item := _normalize_additive_item(raw_item)) is not None
    ]
    return normalized_block


def _normalize_resident_relevance_field(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    raw_value = value.get("value")
    if not isinstance(raw_value, str):
        return None

    normalized_value = raw_value.strip()
    if not normalized_value:
        return None

    normalized: dict[str, Any] = {"value": normalized_value}
    raw_confidence = value.get("confidence")
    if isinstance(raw_confidence, str):
        normalized_confidence = raw_confidence.strip().lower()
        if normalized_confidence in {"high", "medium", "low"}:
            normalized["confidence"] = normalized_confidence

    normalized_evidence = _normalize_additive_evidence_references_v2(value.get("evidence_references_v2"))
    if normalized_evidence:
        normalized["evidence_references_v2"] = normalized_evidence

    return normalized


def _resident_impact_tag_order_key(tag: Mapping[str, Any]) -> tuple[int, str]:
    normalized_tag = str(tag["tag"]).strip().lower()
    return (_RESIDENT_RELEVANCE_IMPACT_TAG_ORDER[normalized_tag], normalized_tag)


def _normalize_resident_relevance_impact_tags(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None

    normalized_tags: dict[str, dict[str, Any]] = {}
    for raw_tag in value:
        if not isinstance(raw_tag, Mapping):
            continue

        raw_value = raw_tag.get("tag")
        if not isinstance(raw_value, str):
            continue

        normalized_value = raw_value.strip().lower()
        if normalized_value not in _RESIDENT_RELEVANCE_IMPACT_TAG_ORDER:
            continue

        normalized: dict[str, Any] = {"tag": normalized_value}
        raw_confidence = raw_tag.get("confidence")
        if isinstance(raw_confidence, str):
            normalized_confidence = raw_confidence.strip().lower()
            if normalized_confidence in {"high", "medium", "low"}:
                normalized["confidence"] = normalized_confidence

        normalized_evidence = _normalize_additive_evidence_references_v2(raw_tag.get("evidence_references_v2"))
        if normalized_evidence:
            normalized["evidence_references_v2"] = normalized_evidence

        normalized_tags[normalized_value] = normalized

    if not normalized_tags:
        return None

    return sorted(normalized_tags.values(), key=_resident_impact_tag_order_key)


def _normalize_resident_relevance_mapping(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    normalized: dict[str, Any] = {}
    for field_name in _RESIDENT_RELEVANCE_FIELD_NAMES:
        normalized_field = _normalize_resident_relevance_field(value.get(field_name))
        if normalized_field is not None:
            normalized[field_name] = normalized_field

    normalized_tags = _normalize_resident_relevance_impact_tags(value.get("impact_tags"))
    if normalized_tags:
        normalized["impact_tags"] = normalized_tags

    return normalized or None


def _sanitize_resident_relevance_block(
    block_value: object,
    *,
    enabled: bool,
) -> tuple[object, bool]:
    if not isinstance(block_value, Mapping):
        return block_value, False

    raw_items = block_value.get("items")
    if not isinstance(raw_items, list):
        return dict(block_value), False

    found_resident_relevance = False
    normalized_items: list[object] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            normalized_items.append(raw_item)
            continue

        normalized_item = {
            key: item_value
            for key, item_value in raw_item.items()
            if key not in {*_RESIDENT_RELEVANCE_FIELD_NAMES, "impact_tags"}
        }
        normalized_resident_relevance = _normalize_resident_relevance_mapping(raw_item)
        if normalized_resident_relevance is not None:
            found_resident_relevance = True
            if enabled:
                normalized_item.update(normalized_resident_relevance)
        normalized_items.append(normalized_item)

    normalized_block = dict(block_value)
    normalized_block["items"] = normalized_items
    return normalized_block, found_resident_relevance


def _merge_resident_relevance_fields(
    *,
    payload: dict[str, Any],
    resident_relevance_api_settings: MeetingDetailResidentRelevanceApiSettings,
) -> dict[str, Any]:
    sanitized_payload = dict(payload)

    normalized_top_level = _normalize_resident_relevance_mapping(payload.get("structured_relevance"))
    sanitized_payload.pop("structured_relevance", None)
    if resident_relevance_api_settings.enabled and normalized_top_level is not None:
        sanitized_payload["structured_relevance"] = normalized_top_level

    for block_name in ("planned", "outcomes"):
        if block_name not in sanitized_payload:
            continue
        sanitized_block, _ = _sanitize_resident_relevance_block(
            sanitized_payload[block_name],
            enabled=resident_relevance_api_settings.enabled,
        )
        sanitized_payload[block_name] = sanitized_block

    return sanitized_payload


def _extract_additive_blocks(*, detail: object) -> dict[str, object]:
    blocks: dict[str, object] = {}
    additive_blocks = getattr(detail, "additive_blocks", None)
    if additive_blocks is not None:
        if not isinstance(additive_blocks, Mapping):
            raise ValueError("Meeting detail additive_blocks must be a mapping when provided")
        for block_name in _ADDITIVE_BLOCK_FIELD_NAMES:
            block_value = additive_blocks.get(block_name)
            normalized = _normalize_additive_block(block_name=block_name, block_value=block_value)
            if normalized is not None:
                blocks[block_name] = normalized

    for block_name in _ADDITIVE_BLOCK_FIELD_NAMES:
        block_value = getattr(detail, block_name, None)
        normalized = _normalize_additive_block(block_name=block_name, block_value=block_value)
        if normalized is not None:
            blocks[block_name] = normalized

    return blocks


def _merge_additive_blocks(
    *,
    payload: dict[str, Any],
    detail: object,
    additive_api_settings: MeetingDetailAdditiveApiSettings,
) -> dict[str, Any]:
    candidate_blocks = _extract_additive_blocks(detail=detail)
    if not candidate_blocks:
        return payload

    if not additive_api_settings.enabled:
        offending_blocks = ", ".join(sorted(candidate_blocks))
        raise ValueError(
            "ST022 additive reader parity guard blocked additive leakage while "
            "ST022_API_ADDITIVE_V1_FIELDS_ENABLED=false; "
            f"offending_blocks={offending_blocks}"
        )

    enabled_blocks = set(additive_api_settings.enabled_blocks)
    disallowed_blocks = sorted(block_name for block_name in candidate_blocks if block_name not in enabled_blocks)
    if disallowed_blocks:
        allowed_blocks = ", ".join(additive_api_settings.enabled_blocks)
        offending_blocks = ", ".join(disallowed_blocks)
        raise ValueError(
            "ST022 additive reader parity guard blocked additive leakage for disabled blocks; "
            f"offending_blocks={offending_blocks}; allowed_blocks={allowed_blocks}"
        )

    payload.update(candidate_blocks)
    return payload


def get_profile_service(request: Request) -> UserProfileService:
    return request.app.state.profile_service


def get_meeting_read_repository(request: Request) -> MeetingReadRepository:
    return request.app.state.meeting_read_repository


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def _city_access_denied_response() -> JSONResponse:
    return JSONResponse(status_code=403, content=CITY_ACCESS_DENIED_BODY)


def _meeting_not_found_response(meeting_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "not_found",
                "message": "Meeting not found",
                "details": {"meeting_id": meeting_id},
            }
        },
    )


@router.get("/cities/{city_id}/meetings")
def get_city_meetings(
    city_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[UserProfileService, Depends(get_profile_service)],
    repository: Annotated[MeetingReadRepository, Depends(get_meeting_read_repository)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
) -> CityMeetingsListResponse:
    profile = profile_service.get_profile(user.user_id)
    if profile.home_city_id is None or profile.home_city_id != city_id:
        return _city_access_denied_response()

    parsed_cursor: MeetingListCursor | None = None
    if cursor is not None:
        try:
            parsed_cursor = MeetingListCursor.from_token(cursor)
        except InvalidMeetingListCursorError:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid cursor",
                        "details": {"cursor": cursor},
                    }
                },
            )

    page = repository.list_city_meetings(
        city_id=city_id,
        limit=limit,
        cursor=parsed_cursor,
        publication_status=status,
    )
    return CityMeetingsListResponse(
        items=[
            MeetingListItemResponse(
                id=item.id,
                city_id=item.city_id,
                city_name=item.city_name,
                meeting_uid=item.meeting_uid,
                title=item.title,
                created_at=item.created_at,
                updated_at=item.updated_at,
                meeting_date=item.meeting_date,
                body_name=item.body_name,
                status=item.publication_status,
                confidence_label=item.confidence_label,
                reader_low_confidence=item.reader_low_confidence,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor.to_token() if page.next_cursor is not None else None,
        limit=limit,
    )


@router.get("/meetings/{meeting_id}")
def get_meeting_detail(
    meeting_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[UserProfileService, Depends(get_profile_service)],
    repository: Annotated[MeetingReadRepository, Depends(get_meeting_read_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> MeetingDetailResponse:
    profile = profile_service.get_profile(user.user_id)
    if profile.home_city_id is None:
        return _city_access_denied_response()

    detail = repository.get_meeting_detail_for_city(
        meeting_id=meeting_id,
        city_id=profile.home_city_id,
        include_additive_blocks=settings.meeting_detail_additive_api.enabled,
    )
    if detail is None:
        return _meeting_not_found_response(meeting_id)

    claims = [
        MeetingClaimResponse(
            id=claim.id,
            claim_order=claim.claim_order,
            claim_text=claim.claim_text,
            evidence=[
                MeetingEvidencePointerResponse(
                    id=evidence.id,
                    artifact_id=evidence.artifact_id,
                    source_document_url=evidence.source_document_url,
                    section_ref=evidence.section_ref,
                    char_start=evidence.char_start,
                    char_end=evidence.char_end,
                    excerpt=evidence.excerpt,
                    document_id=evidence.document_id,
                    span_id=evidence.span_id,
                    document_kind=evidence.document_kind,
                    section_path=evidence.section_path,
                    precision=evidence.precision,
                    confidence=evidence.confidence,
                )
                for evidence in claim.evidence
            ],
        )
        for claim in detail.claims
    ]

    payload = MeetingDetailResponse(
        id=detail.id,
        city_id=detail.city_id,
        city_name=detail.city_name,
        meeting_uid=detail.meeting_uid,
        title=detail.title,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        meeting_date=detail.meeting_date,
        body_name=detail.body_name,
        source_document_kind=detail.source_document_kind,
        source_document_url=detail.source_document_url,
        status=detail.publication_status,
        confidence_label=detail.confidence_label,
        reader_low_confidence=detail.reader_low_confidence,
        publication_id=detail.publication_id,
        published_at=detail.published_at,
        summary=detail.summary_text,
        key_decisions=list(detail.key_decisions),
        key_actions=list(detail.key_actions),
        notable_topics=list(detail.notable_topics),
        evidence_references_v2=_build_evidence_references_v2(claims),
        evidence_references=(
            _build_evidence_references(claims)
            if settings.meeting_detail_legacy_evidence_references_enabled
            else []
        ),
        claims=claims,
    ).model_dump()
    if detail.structured_relevance is not None:
        payload["structured_relevance"] = dict(detail.structured_relevance)
    payload = _merge_additive_blocks(
        payload=payload,
        detail=detail,
        additive_api_settings=settings.meeting_detail_additive_api,
    )
    payload = _merge_resident_relevance_fields(
        payload=payload,
        resident_relevance_api_settings=settings.meeting_detail_resident_relevance_api,
    )
    return _merge_follow_up_prompt_suggestions(
        payload=payload,
        detail=detail,
        follow_up_prompts_api_settings=settings.meeting_detail_follow_up_prompts_api,
    )