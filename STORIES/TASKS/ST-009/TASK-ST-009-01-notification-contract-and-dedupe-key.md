# Notification Contract and Dedupe Key

**Task ID:** TASK-ST-009-01  
**Story:** ST-009  
**Bucket:** backend  
**Requirement Links:** MVP 4.4(1-4), FR-5, NFR-1, NFR-2, NFR-4

## Objective
Define and lock the notification event contract and deterministic dedupe key format used by enqueue and delivery workers.

## Scope
- In scope:
  - Event payload shape for fan-out and worker processing.
  - Dedupe key rule: user_id + meeting_id + notification_type.
  - Status model for delivery lifecycle.
- Out of scope:
  - Actual DB migration and worker implementation.

## Inputs / Dependencies
- ST-002 subscription model
- ST-005 publish completion event
- ST-008 push subscription storage

## Implementation Notes
- Document contract in one canonical backend spec file.
- Include explicit version field for payload evolution.
- Define invalid/expired subscription handling semantics for downstream tasks.

## Acceptance Criteria
1. Contract document includes required and optional fields with types.
2. Dedupe key algorithm is deterministic and collision-safe for story scope.
3. Delivery status transitions are defined and unambiguous.

## Validation
- Run unit test for dedupe key generation determinism and uniqueness.
- Run contract schema validation test with one valid and one invalid payload sample.
- Team review signoff on status transition table.

## Deliverables
- Contract spec document committed.
- Dedupe key helper interface signature committed.
- Contract tests added and passing.
