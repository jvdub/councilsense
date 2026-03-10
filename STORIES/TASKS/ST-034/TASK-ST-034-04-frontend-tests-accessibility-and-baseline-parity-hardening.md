# Frontend Tests, Accessibility, and Baseline Parity Hardening

**Task ID:** TASK-ST-034-04  
**Story:** ST-034  
**Bucket:** tests  
**Requirement Links:** ST-034 Acceptance Criteria #4 and #5, REQUIREMENTS §13.5 Clarity Outcome, REQUIREMENTS §14(3,10)

## Objective

Add frontend tests and accessibility checks that verify resident scan-card rendering, baseline parity, and sparse-data handling.

## Scope

- Add verification coverage for resident-relevance enabled and disabled states.
- Validate sparse-data and no-data card behavior.
- Add accessibility and baseline parity checks for the additive scan layer.
- Out of scope: backend serialization validation and follow-up prompt behavior.

## Inputs / Dependencies

- TASK-ST-034-02 card rendering.
- TASK-ST-034-03 navigation and empty-state behavior.
- Existing meeting detail verification patterns from ST-007 and ST-028.

## Implementation Notes

- Keep tests focused on additive rendering and fallback safety.
- Verify no unexpected regressions in baseline meeting detail snapshots or assertions.
- Include keyboard and accessible-name coverage for new interactive affordances.

## Acceptance Criteria

1. Frontend tests cover additive rendering, flag-off parity, and sparse-data cases.
2. Accessibility checks cover new scan-card controls and headings.
3. Baseline meeting detail behavior remains equivalent when the feature is disabled.
4. Verification evidence is sufficient for rollout review.

## Validation

- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
- Run meeting detail verification suites with resident-relevance flags on and off.

## Deliverables

- Frontend test coverage for resident scan cards.
- Accessibility and baseline parity verification notes.
- Representative additive-mode verification evidence.
