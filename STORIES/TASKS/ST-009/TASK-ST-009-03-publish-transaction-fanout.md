# Publish Transaction Fan-Out

**Task ID:** TASK-ST-009-03  
**Story:** ST-009  
**Bucket:** backend  
**Requirement Links:** MVP 4.4(1-2), FR-5, NFR-1

## Objective
Write notification outbox rows inside the successful publish transaction for eligible city subscribers.

## Scope
- In scope:
  - Eligibility selection by city and active subscription.
  - Outbox row creation in publish flow.
  - Idempotent conflict behavior for duplicate enqueue attempts.
- Out of scope:
  - Actual push provider delivery.
  - Retry loop processing.

## Inputs / Dependencies
- TASK-ST-009-01
- TASK-ST-009-02
- ST-005 publish completion hook

## Implementation Notes
- Ensure publish success and outbox write are transactionally consistent.
- Do not enqueue for suppressed/invalid subscriptions.
- Emit lightweight structured event on enqueue success/failure.

## Acceptance Criteria
1. Successful publish enqueues one logical outbox row per eligible user.
2. Repeated enqueue call for same meeting and type does not duplicate logical delivery.
3. Failed outbox write fails transaction or follows explicit rollback-safe policy.

## Validation
- Run integration test: publish creates expected outbox rows.
- Run integration test: duplicate publish trigger remains idempotent.
- Run negative test: invalid subscription not enqueued.

## Deliverables
- Backend service changes in publish path.
- Integration tests for enqueue idempotency and eligibility.
- Brief ops note describing enqueue conflict behavior.
