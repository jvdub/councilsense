from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.api.profile import UserProfileService
from councilsense.db import InvalidMeetingListCursorError, MeetingListCursor, MeetingReadRepository


router = APIRouter(prefix="/v1", tags=["meetings"])


class MeetingListItemResponse(BaseModel):
    id: str
    city_id: str
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    status: str | None
    confidence_label: str | None


class CityMeetingsListResponse(BaseModel):
    items: list[MeetingListItemResponse]
    next_cursor: str | None
    limit: int


class MeetingEvidencePointerResponse(BaseModel):
    id: str
    artifact_id: str
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str


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
    publication_id: str | None
    published_at: str | None
    summary: str | None
    key_decisions: list[str]
    key_actions: list[str]
    notable_topics: list[str]
    claims: list[MeetingClaimResponse]


def get_profile_service(request: Request) -> UserProfileService:
    return request.app.state.profile_service


def get_meeting_read_repository(request: Request) -> MeetingReadRepository:
    return request.app.state.meeting_read_repository


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
    if profile.home_city_id != city_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "forbidden",
                    "message": "City access denied",
                    "details": {"city_id": city_id},
                }
            },
        )

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
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor.to_token() if page.next_cursor is not None else None,
        limit=limit,
    )


@router.get("/meetings/{meeting_id}")
def get_meeting_detail(
    meeting_id: str,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[MeetingReadRepository, Depends(get_meeting_read_repository)],
) -> MeetingDetailResponse:
    detail = repository.get_meeting_detail(meeting_id=meeting_id)
    if detail is None:
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

    return MeetingDetailResponse(
        id=detail.id,
        city_id=detail.city_id,
        meeting_uid=detail.meeting_uid,
        title=detail.title,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        status=detail.publication_status,
        confidence_label=detail.confidence_label,
        publication_id=detail.publication_id,
        published_at=detail.published_at,
        summary=detail.summary_text,
        key_decisions=list(detail.key_decisions),
        key_actions=list(detail.key_actions),
        notable_topics=list(detail.notable_topics),
        claims=[
            MeetingClaimResponse(
                id=claim.id,
                claim_order=claim.claim_order,
                claim_text=claim.claim_text,
                evidence=[
                    MeetingEvidencePointerResponse(
                        id=evidence.id,
                        artifact_id=evidence.artifact_id,
                        section_ref=evidence.section_ref,
                        char_start=evidence.char_start,
                        char_end=evidence.char_end,
                        excerpt=evidence.excerpt,
                    )
                    for evidence in claim.evidence
                ],
            )
            for claim in detail.claims
        ],
    )