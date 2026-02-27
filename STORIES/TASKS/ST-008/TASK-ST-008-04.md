# Subscription API Wiring and Recovery State Mapping

**Task ID:** TASK-ST-008-04  
**Story:** ST-008  
**Bucket:** backend  
**Requirement Links:** MVP §4.4(4-5), FR-5(4-5), NFR-3

## Objective
Integrate UI push actions with backend subscription CRUD and surface invalid/expired/suppressed states with recoverable actions.

## Scope (+ Out of scope)
- Wire create/read/delete subscription API calls to frontend flow contracts.
- Map backend subscription lifecycle states to UI-facing state model.
- Implement recovery action hooks for invalid/expired/suppressed subscriptions.
- Out of scope: notification send pipeline retry policy.

## Inputs / Dependencies
- TASK-ST-008-01.
- TASK-ST-008-03 push UI flow.
- Existing subscription backend endpoints.

## Implementation Notes
- Keep state mapping centralized to avoid drift.
- Ensure idempotent behavior for repeated subscribe/unsubscribe clicks.
- Preserve clear state transitions for diagnostics.

## Acceptance Criteria
1. UI actions create and remove backend subscription records correctly.
2. Invalid/expired/suppressed states are surfaced consistently.
3. Recovery actions trigger expected remediation path.

## Validation
- Run integration tests with mocked backend state transitions.
- Verify subscription record changes in test environment.

## Deliverables
- Subscription client/service integration and state mapper.
- Integration tests for CRUD and recovery transitions.
