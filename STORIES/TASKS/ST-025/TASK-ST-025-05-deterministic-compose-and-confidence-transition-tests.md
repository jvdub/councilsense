# Deterministic Compose and Confidence Transition Tests

**Task ID:** TASK-ST-025-05  
**Story:** ST-025  
**Bucket:** tests  
**Requirement Links:** ST-025 Acceptance Criteria #1, #3, #4, and #5, AGENDA_PLAN §5 Phase 1, NFR-4

## Objective
Add end-to-end and integration test coverage proving deterministic compose behavior and correct limited-confidence transitions under conflict and partial-source conditions.

## Scope
- Add integration tests spanning compose -> authority policy -> publish decision path.
- Verify deterministic source ordering, authority-preferred outcomes, and reason-code persistence.
- Validate publish continuity for partial-source meetings with explicit confidence state.
- Out of scope: frontend mismatch rendering and notification fanout behavior.

## Inputs / Dependencies
- TASK-ST-025-03 limited-confidence publish wiring.
- TASK-ST-025-04 conflict/partial-coverage fixture catalog.
- Existing backend integration and smoke test command pathways.

## Implementation Notes
- Include rerun assertions to verify idempotent, deterministic confidence outcomes.
- Assert both status and reason-code vectors to prevent silent policy drift.
- Capture evidence artifacts suitable for story completion and rollout gating review.

## Acceptance Criteria
1. Tests verify deterministic compose ordering across reruns.
2. Tests verify minutes-authoritative outcomes when minutes are available.
3. Tests verify `limited_confidence` transitions and reason codes for conflict/weak/missing scenarios.
4. Tests verify partial-source publish continuity with explicit confidence labels.

## Validation
- `pytest -q backend/tests -k "compose or confidence or authority"`
- Execute local runtime smoke for a pilot-city fixture set and compare publish outputs.
- Store test artifact summary for AC #5 completion evidence.

## Deliverables
- Integration/e2e test modules for compose and confidence policy.
- Determinism assertions for status + reason-code outputs.
- Story-level validation report aligned to ST-025 acceptance criteria.
