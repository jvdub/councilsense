# Idempotency, Retry, and Failure Validation

**Task ID:** TASK-ST-009-05  
**Story:** ST-009  
**Bucket:** tests  
**Requirement Links:** FR-5, NFR-1, NFR-2, NFR-4

## Objective
Add focused end-to-end validation coverage proving one logical delivery per user and auditable failure behavior.

## Scope
- In scope:
  - End-to-end tests from publish to delivery state.
  - Assertions on dedupe, retries, and suppression.
  - Evidence query snippets for operations verification.
- Out of scope:
  - New feature behavior changes.

## Inputs / Dependencies
- TASK-ST-009-03
- TASK-ST-009-04

## Implementation Notes
- Use deterministic fixtures for city, meeting, user, and subscriptions.
- Include one transient provider failure scenario and one invalid endpoint scenario.
- Keep test runtime bounded and repeatable.

## Acceptance Criteria
1. End-to-end test confirms at most one logical delivery per dedupe key.
2. Retry path and max-attempt cutoff are verified.
3. Suppressed endpoints are excluded from future sends.
4. Attempt log rows contain triage-useful metadata.

## Validation
- Run targeted notification test suite.
- Run one repeat execution to confirm idempotent behavior on rerun.
- Capture and store test evidence summary for story signoff.

## Deliverables
- End-to-end and integration tests.
- Validation evidence artifact with pass/fail outcomes.
- Story-level verification checklist update.
