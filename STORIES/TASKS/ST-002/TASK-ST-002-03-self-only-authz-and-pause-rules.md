# Enforce self-only authz and pause rules

**Task ID:** TASK-ST-002-03  
**Story:** ST-002  
**Bucket:** backend  
**Requirement Links:** FR-5(4), FR-6, NFR-3

## Objective
Guarantee profile updates are self-scoped and expose deterministic pause/unsubscribe eligibility for downstream fan-out.

## Scope
- Enforce self-only policy for profile reads/updates.
- Implement pause-window active/inactive evaluation helper.
- Expose effective notification eligibility state for downstream use.
- Out of scope: notification delivery worker implementation.

## Inputs / Dependencies
- TASK-ST-002-02

## Implementation Notes
- Target authorization policy layer and profile domain service.
- Keep pause-window semantics explicit and timezone-safe.

## Acceptance Criteria
1. Any attempt to read/write another user profile is blocked.
2. Active pause window marks user as ineligible for notifications.
3. Disabled notifications also mark user as ineligible.

## Validation
- Run authz tests for cross-user access attempts.
- Run unit tests for pause window boundary conditions.

## Deliverables
- Authorization policy updates and notification eligibility logic.
