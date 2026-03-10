# Frontend Tests, Accessibility, and Latency Regression Checks

**Task ID:** TASK-ST-028-05  
**Story:** ST-028  
**Bucket:** tests  
**Requirement Links:** ST-028 Acceptance Criteria #5, AGENDA_PLAN §5 Phase 3, AGENDA_PLAN §6 Testing and validation plan

## Objective

Add and run frontend verification coverage for baseline/additive states, mismatch severity rendering, accessibility checks, and latency-regression guardrails.

## Scope

- Add component/integration tests for flag-off baseline mode and flag-on additive mode.
- Add tests for fallback behavior when additive fields are missing/partial.
- Add mismatch severity and neutral/empty-state rendering tests.
- Add lightweight accessibility and latency-regression checks for meeting detail route.
- Out of scope: broad frontend redesign testing outside meeting detail surface.

## Inputs / Dependencies

- TASK-ST-028-04 integrated additive + baseline rendering behavior.
- Existing frontend test harness and meeting detail fixtures.
- Team latency budget and accessibility baseline for meeting detail route.

## Implementation Notes

- Keep test fixtures explicit for each mode and mismatch state.
- Include assertions that prevent accidental rendering of mismatch indicators without evidence support.
- Ensure checks are CI-friendly and deterministic.

## Acceptance Criteria

1. Tests cover flag-off baseline parity, flag-on additive rendering, and fallback behavior.
2. Tests cover mismatch severity and no-evidence suppression behavior.
3. Accessibility checks validate new additive sections do not degrade baseline accessibility.
4. Latency-regression checks confirm meeting detail remains within agreed budget.

## Validation

- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
- Execute documented accessibility and latency checks against representative payloads.

## Deliverables

- Frontend test cases and fixture updates.
- Accessibility and latency verification notes.
- Story-level validation evidence bundle for rollout readiness.
