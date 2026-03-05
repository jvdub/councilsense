# Promotion Criteria and Consecutive Green Gate Checks

**Task ID:** TASK-ST-021-04  
**Story:** ST-021  
**Bucket:** tests  
**Requirement Links:** ST-021 Acceptance Criteria #4, GAP_PLAN §Gate Matrix (A/B/C), NFR-4

## Objective

Implement promotion checks that require two consecutive green fixture runs across Gate A/B/C prerequisites before expanding enforcement scope.

## Scope

- Define promotion eligibility algorithm using fixture scorecard outcomes.
- Track consecutive green state with clear reset behavior after failures.
- Define promotion artifact that records window, run IDs, and gate status.
- Out of scope: executing rollback controls and modifying enforced publish policy hooks.

## Inputs / Dependencies

- TASK-ST-021-01 flag and cohort configuration contract.
- TASK-ST-021-02 shadow diagnostics output.
- ST-017 fixture scorecard execution outputs.

## Implementation Notes

- Promotion should be blocked unless Gate A/B/C are all green in two consecutive runs.
- Reset consecutive counter on any gate failure or missing result.
- Keep promotion evidence immutable for release review.

## Acceptance Criteria

1. Promotion logic requires two consecutive green runs across Gate A/B/C.
2. Any failed or missing gate result resets consecutive-green progression.
3. Promotion artifact records run IDs, gate outcomes, and eligibility decision.
4. Promotion checks are usable in pre-enforcement release reviews.

## Validation

- Replay fixture histories covering pass-pass, pass-fail-pass, and fail-pass-pass sequences.
- Verify promotion eligibility only for qualifying consecutive-green sequences.
- Confirm promotion artifacts are complete and reproducible for review.

## Deliverables

- Promotion eligibility rules specification.
- Consecutive-green check implementation notes with scenario matrix.
- Promotion evidence artifact template and example output.
