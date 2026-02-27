# ST-008 End-to-End Settings and Push Flow Tests

**Task ID:** TASK-ST-008-05  
**Story:** ST-008  
**Bucket:** tests  
**Requirement Links:** MVP §4.4(2-5), FR-5(4-5), NFR-3

## Objective
Add focused automated test coverage for notification settings persistence, push subscribe/unsubscribe, and recovery-state UX.

## Scope (+ Out of scope)
- Add integration/e2e tests for settings persistence across sessions.
- Add tests for subscribe/unsubscribe happy paths.
- Add tests for invalid/expired/suppressed recovery behavior.
- Out of scope: email notification controls.

## Inputs / Dependencies
- TASK-ST-008-02, TASK-ST-008-03, TASK-ST-008-04.
- Stable test fixtures for subscription lifecycle states.

## Implementation Notes
- Use deterministic mocks for permission and subscription states.
- Assert user-visible recovery affordances for each degraded state.
- Keep suite scoped to MVP push channel behavior.

## Acceptance Criteria
1. Test suite covers persistence and primary push actions.
2. Recovery-state tests verify visibility and actionable remediation.
3. Regressions in push/settings flows are caught in CI.

## Validation
- Run targeted frontend integration/e2e tests for notification settings and push flows.
- Capture pass/fail artifacts for story acceptance.

## Deliverables
- New/updated automated tests and fixtures.
- Story validation evidence entry summarizing executed checks.
