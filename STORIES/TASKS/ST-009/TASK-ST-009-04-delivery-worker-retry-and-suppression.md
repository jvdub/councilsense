# Delivery Worker Retry and Suppression

**Task ID:** TASK-ST-009-04  
**Story:** ST-009  
**Bucket:** backend  
**Requirement Links:** MVP 4.4(3-4), FR-5, NFR-1, NFR-2, NFR-4

## Objective
Implement worker processing that sends notifications with bounded retry/backoff and suppresses invalid or expired subscriptions.

## Scope
- In scope:
  - Worker polling and state transitions.
  - Configurable max attempts and backoff schedule.
  - Suppression state updates for invalid/expired endpoints.
  - Attempt-level persistence updates.
- Out of scope:
  - Dashboarding and alerting panels.

## Inputs / Dependencies
- TASK-ST-009-01
- TASK-ST-009-02

## Implementation Notes
- Separate transient errors from terminal invalid-subscription errors.
- Persist next_retry_at only for retry-eligible failures.
- Keep worker logic safe under concurrent runners.

## Acceptance Criteria
1. Transient send failures retry until max attempts then terminal failure.
2. Invalid/expired subscription responses mark subscription suppressed.
3. Each send attempt creates an audit row with outcome metadata.
4. Worker remains idempotent under duplicate queue visibility.

## Validation
- Run worker integration test for retry progression and terminal fail.
- Run worker integration test for invalid-subscription suppression.
- Run concurrency test with two worker instances against same pending rows.

## Deliverables
- Worker code updates for retry/backoff.
- Subscription suppression update path.
- Integration tests for retry, suppression, and concurrency safety.
