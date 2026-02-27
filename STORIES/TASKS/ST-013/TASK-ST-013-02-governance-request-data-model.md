# Governance Request Data Model and Lifecycle

**Task ID:** TASK-ST-013-02  
**Story:** ST-013  
**Bucket:** data  
**Requirement Links:** NFR-3, NFR-7

## Objective
Implement schema and state models for retention policy, export requests, and deletion/anonymization requests.

## Scope
- Add persistence for:
  - export requests and status history
  - deletion requests and status history
  - retention policy configuration and effective dates
  - governance audit trail metadata
- Define allowed state transitions and constraints.
- Out of scope: request execution workers and user-facing UI.

## Inputs / Dependencies
- TASK-ST-013-01 policy outputs.
- Existing user/profile/notification data models.

## Implementation Notes
- Include idempotency keys for request creation to avoid duplicate requests.
- Preserve append-only audit events for status changes.
- Enforce referential integrity to user identity records.

## Acceptance Criteria
1. Export and deletion request records can be created and tracked through lifecycle states.
2. Invalid state transitions are rejected.
3. Retention policy values are configurable without schema rework.
4. Audit trail entries are immutable and queryable.

## Validation
- Run migration and rollback checks in local/dev DB.
- Add schema-level tests for constraints and transitions.
- Verify duplicate request protection via idempotency key tests.

## Deliverables
- Migration files and updated data model definitions.
- State-transition documentation.
- Automated tests for lifecycle and integrity constraints.
