from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.app.notification_dlq_replay import NotificationDlqReplayNotFoundError, NotificationDlqReplayService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/operators/notifications/dlq", tags=["notification-replay"])


class ReplayDlqRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    override_permanent_invalid: bool = False


class ReplayDlqResponse(BaseModel):
    dlq_id: int
    source_outbox_id: str
    replay_outbox_id: str | None
    requeue_correlation_id: str
    replay_idempotency_key: str
    actor_user_id: str
    replay_reason: str
    outcome: str
    outcome_detail: str | None
    created_at: str


def get_notification_dlq_replay_service(request: Request) -> NotificationDlqReplayService:
    return request.app.state.notification_dlq_replay_service


def require_operator_user(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    allowed_user_ids = set(request.app.state.settings.notification_replay_operator_user_ids)
    if user.user_id not in allowed_user_ids:
        logger.warning(
            "notification_dlq_replay_unauthorized",
            extra={
                "event": {
                    "event_name": "notification_dlq_replay_unauthorized",
                    "actor_user_id": user.user_id,
                    "path": str(request.url.path),
                }
            },
        )
        raise HTTPException(status_code=403, detail="Operator replay action is forbidden")
    return user


@router.post("/{dlq_outbox_id}/replay", response_model=ReplayDlqResponse, status_code=201)
def replay_dlq_item(
    dlq_outbox_id: str,
    payload: ReplayDlqRequestBody,
    http_response: Response,
    operator_user: Annotated[AuthenticatedUser, Depends(require_operator_user)],
    service: Annotated[NotificationDlqReplayService, Depends(get_notification_dlq_replay_service)],
) -> ReplayDlqResponse:
    try:
        result = service.replay(
            dlq_outbox_id=dlq_outbox_id,
            replay_idempotency_key=payload.idempotency_key,
            actor_user_id=operator_user.user_id,
            replay_reason=payload.reason,
            override_permanent_invalid=payload.override_permanent_invalid,
        )
    except NotificationDlqReplayNotFoundError as exc:
        raise HTTPException(status_code=404, detail="DLQ item not found") from exc

    if result.outcome == "ineligible":
        raise HTTPException(status_code=409, detail=result.outcome_detail or "DLQ replay ineligible")

    payload_response = ReplayDlqResponse(
        dlq_id=result.dlq_id,
        source_outbox_id=result.source_outbox_id,
        replay_outbox_id=result.replay_outbox_id,
        requeue_correlation_id=result.requeue_correlation_id,
        replay_idempotency_key=result.replay_idempotency_key,
        actor_user_id=result.actor_user_id,
        replay_reason=result.replay_reason,
        outcome=result.outcome,
        outcome_detail=result.outcome_detail,
        created_at=result.created_at,
    )

    http_response.status_code = 201 if result.outcome == "requeued" else 200
    return payload_response
