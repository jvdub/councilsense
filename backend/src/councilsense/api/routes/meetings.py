from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.api.profile import UserProfileService
from councilsense.db import InvalidMeetingListCursorError, MeetingListCursor, MeetingReadRepository


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
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
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
    document_kind: str | None = Field(default=None, exclude=True)
    section_path: str | None = Field(default=None, exclude=True)
    precision: str | None = Field(default=None, exclude=True)


class MeetingClaimResponse(BaseModel):
    id: str
    claim_order: int
    claim_text: str
    evidence: list[MeetingEvidencePointerResponse]


class MeetingDetailResponse(BaseModel):
    id: str
    city_id: str
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    status: str | None
    confidence_label: str | None
    reader_low_confidence: bool
    publication_id: str | None
    published_at: str | None
    summary: str | None
    key_decisions: list[str]
    key_actions: list[str]
    notable_topics: list[str]
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


def _prefer_evidence_pointer(
    *,
    current: MeetingEvidencePointerResponse,
    challenger: MeetingEvidencePointerResponse,
) -> MeetingEvidencePointerResponse:
    if _evidence_order_key(challenger) < _evidence_order_key(current):
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


def get_profile_service(request: Request) -> UserProfileService:
    return request.app.state.profile_service


def get_meeting_read_repository(request: Request) -> MeetingReadRepository:
    return request.app.state.meeting_read_repository


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
                meeting_uid=item.meeting_uid,
                title=item.title,
                created_at=item.created_at,
                updated_at=item.updated_at,
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
) -> MeetingDetailResponse:
    profile = profile_service.get_profile(user.user_id)
    if profile.home_city_id is None:
        return _city_access_denied_response()

    detail = repository.get_meeting_detail_for_city(
        meeting_id=meeting_id,
        city_id=profile.home_city_id,
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
                    document_kind=evidence.document_kind,
                    section_path=evidence.section_path,
                    precision=evidence.precision,
                )
                for evidence in claim.evidence
            ],
        )
        for claim in detail.claims
    ]

    return MeetingDetailResponse(
        id=detail.id,
        city_id=detail.city_id,
        meeting_uid=detail.meeting_uid,
        title=detail.title,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        status=detail.publication_status,
        confidence_label=detail.confidence_label,
        reader_low_confidence=detail.reader_low_confidence,
        publication_id=detail.publication_id,
        published_at=detail.published_at,
        summary=detail.summary_text,
        key_decisions=list(detail.key_decisions),
        key_actions=list(detail.key_actions),
        notable_topics=list(detail.notable_topics),
        evidence_references=_build_evidence_references(claims),
        claims=claims,
    )