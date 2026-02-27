# Implement scheduler enqueue by enabled city

**Task ID:** TASK-ST-004-01  
**Story:** ST-004  
**Bucket:** backend  
**Requirement Links:** FR-3, FR-7(4), NFR-1

## Objective
Trigger processing runs on cadence by enqueuing one scan job per enabled city.

## Scope
- Add/extend scheduler job to fetch enabled cities and enqueue work.
- Ensure enqueue happens independent of user subscription counts.
- Out of scope: downstream stage execution internals.

## Inputs / Dependencies
- ST-003 registry service for enabled cities

## Implementation Notes
- Target scheduler module/cron entrypoint and queue producer.
- Include idempotency guard if scheduler can overlap.

## Acceptance Criteria
1. Scheduler emits one enqueue action per enabled city each cycle.
2. Cities with zero subscribers are still enqueued.
3. Disabled cities are not enqueued.

## Validation
- Run scheduler unit/integration tests with mocked registry states.
- Verify queue enqueue payload count/content per test scenario.

## Deliverables
- Scheduler enqueue implementation and tests.
