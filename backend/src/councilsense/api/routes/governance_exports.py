from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.app.governance_exports import (
    GovernanceExportArtifactUnavailableError,
    GovernanceExportNotFoundError,
    GovernanceExportOwnershipError,
    GovernanceExportService,
)


router = APIRouter(prefix="/v1/me/exports", tags=["governance-exports"])


class ExportScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_profile: bool = True
    include_preferences: bool = True
    include_notification_history: bool = True


class CreateExportRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    scope: ExportScopeRequest | None = None


class ExportRequestResponse(BaseModel):
    id: str
    status: str
    scope: dict[str, bool]
    artifact_uri: str | None
    error_code: str | None
    completed_at: str | None
    processing_attempt_count: int
    max_processing_attempts: int
    created_at: str
    updated_at: str


class ExportArtifactResponse(BaseModel):
    artifact_uri: str
    schema_version: str
    generated_at: str
    export: dict[str, Any]


def get_governance_export_service(request: Request) -> GovernanceExportService:
    return request.app.state.governance_export_service


@router.post("", response_model=ExportRequestResponse, status_code=201)
def create_export_request(
    payload: CreateExportRequestBody,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[GovernanceExportService, Depends(get_governance_export_service)],
) -> ExportRequestResponse:
    scope = payload.scope.model_dump() if payload.scope is not None else None
    try:
        record = service.create_request(
            user_id=user.user_id,
            idempotency_key=payload.idempotency_key,
            requested_by=user.user_id,
            scope=scope,
        )
    except GovernanceExportOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Export request ownership mismatch") from exc

    return ExportRequestResponse(
        id=record.id,
        status=record.status,
        scope=record.scope,
        artifact_uri=record.artifact_uri,
        error_code=record.error_code,
        completed_at=record.completed_at,
        processing_attempt_count=record.processing_attempt_count,
        max_processing_attempts=record.max_processing_attempts,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/{request_id}", response_model=ExportRequestResponse)
def get_export_request(
    request_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[GovernanceExportService, Depends(get_governance_export_service)],
) -> ExportRequestResponse:
    try:
        record = service.get_request(user_id=user.user_id, request_id=request_id)
    except GovernanceExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Export request not found") from exc
    except GovernanceExportOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Export request ownership mismatch") from exc

    return ExportRequestResponse(
        id=record.id,
        status=record.status,
        scope=record.scope,
        artifact_uri=record.artifact_uri,
        error_code=record.error_code,
        completed_at=record.completed_at,
        processing_attempt_count=record.processing_attempt_count,
        max_processing_attempts=record.max_processing_attempts,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/{request_id}/artifact", response_model=ExportArtifactResponse)
def get_export_artifact(
    request_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[GovernanceExportService, Depends(get_governance_export_service)],
) -> ExportArtifactResponse:
    try:
        artifact = service.get_artifact(user_id=user.user_id, request_id=request_id)
    except GovernanceExportArtifactUnavailableError as exc:
        raise HTTPException(status_code=409, detail="Export artifact not ready") from exc
    except GovernanceExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Export request not found") from exc
    except GovernanceExportOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Export request ownership mismatch") from exc

    return ExportArtifactResponse(
        artifact_uri=artifact.artifact_uri,
        schema_version=artifact.schema_version,
        generated_at=artifact.generated_at,
        export=artifact.payload,
    )
