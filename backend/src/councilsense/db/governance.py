from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


GovernanceExportRequestStatus = Literal[
    "requested",
    "accepted",
    "processing",
    "completed",
    "failed",
    "cancelled",
]

GovernanceDeletionRequestStatus = Literal[
    "requested",
    "accepted",
    "processing",
    "completed",
    "failed",
    "rejected",
    "cancelled",
]

GovernanceDeletionMode = Literal["delete", "anonymize"]


@dataclass(frozen=True)
class GovernanceRequestStatusModel:
    transitions: Mapping[str, tuple[str, ...]]

    def can_transition(self, *, current: str, next_status: str) -> bool:
        allowed = self.transitions.get(current)
        if allowed is None:
            return False
        return next_status in allowed


GOVERNANCE_EXPORT_REQUEST_STATUS_MODEL = GovernanceRequestStatusModel(
    transitions={
        "requested": ("accepted", "cancelled"),
        "accepted": ("processing", "cancelled"),
        "processing": ("completed", "failed", "cancelled"),
        "failed": ("processing", "cancelled"),
        "completed": (),
        "cancelled": (),
    }
)

GOVERNANCE_DELETION_REQUEST_STATUS_MODEL = GovernanceRequestStatusModel(
    transitions={
        "requested": ("accepted", "rejected", "cancelled"),
        "accepted": ("processing", "cancelled"),
        "processing": ("completed", "failed", "cancelled"),
        "failed": ("processing", "cancelled"),
        "completed": (),
        "rejected": (),
        "cancelled": (),
    }
)


@dataclass(frozen=True)
class GovernanceRetentionPolicyRecord:
    id: str
    policy_name: str
    applies_to: str
    retention_days: int
    effective_from: str
    effective_until: str | None
    config_json: str
    created_by: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GovernanceExportRequestRecord:
    id: str
    user_id: str
    idempotency_key: str
    status: GovernanceExportRequestStatus
    requested_by: str
    scope_json: str
    artifact_uri: str | None
    error_code: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GovernanceDeletionRequestRecord:
    id: str
    user_id: str
    idempotency_key: str
    mode: GovernanceDeletionMode
    status: GovernanceDeletionRequestStatus
    requested_by: str
    reason_code: str | None
    due_at: str | None
    completed_at: str | None
    error_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GovernanceRequestStatusHistoryRecord:
    id: int
    request_id: str
    from_status: str | None
    to_status: str
    changed_by: str
    reason: str | None
    metadata_json: str
    changed_at: str


@dataclass(frozen=True)
class GovernanceAuditEventRecord:
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    actor_user_id: str
    metadata_json: str
    created_at: str
