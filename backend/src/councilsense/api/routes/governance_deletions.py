from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.app.governance_deletions import (
    GovernanceDeletionNotFoundError,
    GovernanceDeletionOwnershipError,
    GovernanceDeletionService,
)


router = APIRouter(prefix="/v1/me/deletions", tags=["governance-deletions"])


class CreateDeletionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    mode: Literal["delete", "anonymize"] = "anonymize"
    reason_code: str | None = None


class DeletionRequestResponse(BaseModel):
    id: str
    status: str
    mode: str
    reason_code: str | None
    due_at: str | None
    completed_at: str | None
    error_code: str | None
    created_at: str
    updated_at: str


def get_governance_deletion_service(request: Request) -> GovernanceDeletionService:
    return request.app.state.governance_deletion_service


@router.post("", response_model=DeletionRequestResponse, status_code=201)
def create_deletion_request(
    payload: CreateDeletionRequestBody,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[GovernanceDeletionService, Depends(get_governance_deletion_service)],
) -> DeletionRequestResponse:
    try:
        record = service.create_request(
            user_id=user.user_id,
            idempotency_key=payload.idempotency_key,
            mode=payload.mode,
            requested_by=user.user_id,
            reason_code=payload.reason_code,
        )
    except GovernanceDeletionOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Deletion request ownership mismatch") from exc

    return DeletionRequestResponse(
        id=record.id,
        status=record.status,
        mode=record.mode,
        reason_code=record.reason_code,
        due_at=record.due_at,
        completed_at=record.completed_at,
        error_code=record.error_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/{request_id}", response_model=DeletionRequestResponse)
def get_deletion_request(
    request_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[GovernanceDeletionService, Depends(get_governance_deletion_service)],
) -> DeletionRequestResponse:
    try:
        record = service.get_request(user_id=user.user_id, request_id=request_id)
    except GovernanceDeletionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Deletion request not found") from exc
    except GovernanceDeletionOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Deletion request ownership mismatch") from exc

    return DeletionRequestResponse(
        id=record.id,
        status=record.status,
        mode=record.mode,
        reason_code=record.reason_code,
        due_at=record.due_at,
        completed_at=record.completed_at,
        error_code=record.error_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )