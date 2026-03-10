# Integration Tests for Dedupe, Limits, and Idempotent Retry Behavior

**Task ID:** TASK-ST-038-05  
**Story:** ST-038  
**Bucket:** tests  
**Requirement Links:** ST-038 Acceptance Criteria #1 through #5, FR-3, FR-4, FR-7, NFR-4

## Objective

Lock in on-demand processing admission-control behavior with integration tests for meeting-level dedupe, user limits, and safe terminal-state retries.

## Scope

- Add integration tests for simultaneous same-meeting requests, per-user limit enforcement, and terminal-state reopen behavior.
- Verify active-work dedupe reuses the same active work item across repeated requests.
- Verify retry/reopen flows remain idempotent for artifacts and publications.
- Out of scope: frontend tile rendering and operator replay UI.

## Inputs / Dependencies

- TASK-ST-038-02 admission-control behavior.
- TASK-ST-038-04 terminal-state reopen rules.
- Existing integration-test patterns for run lifecycle and replay safety.

## Implementation Notes

- Include concurrency-shaped scenarios where practical, even if modeled deterministically.
- Assert both API outcomes and persisted lifecycle side effects.
- Keep test fixtures focused on discovered-meeting request flows.

## Acceptance Criteria

1. Tests verify only one active job exists for repeated requests against the same meeting. (ST-038 AC #1 and #3)
2. Tests verify per-user limits behave deterministically. (ST-038 AC #2)
3. Tests verify terminal-state reopen flows remain idempotent for downstream side effects. (ST-038 AC #4 and #5)

## Validation

- `pytest -q`
- Focused backend test selection for on-demand request, dedupe, and retry flows.

## Deliverables

- Integration suite for dedupe, limits, and reopen behavior.
- Deterministic fixtures for simultaneous and repeated-request scenarios.
- Regression protection for meeting-level active-work guarantees.
