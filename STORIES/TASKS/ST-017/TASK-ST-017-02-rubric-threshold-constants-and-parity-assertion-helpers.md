# Rubric Threshold Constants and Parity Assertion Helpers

**Task ID:** TASK-ST-017-02  
**Story:** ST-017  
**Bucket:** backend  
**Requirement Links:** GAP_PLAN §Parity Targets, GAP_PLAN §Gate B, ST-017 Acceptance Criteria #3 and #5

## Objective
Freeze parity thresholds into centralized test constants and expose reusable assertion helpers for all rubric dimensions.

## Scope
- Define one authoritative threshold constant set for parity checks.
- Add helper assertions for section completeness, topic semantics, specificity, grounding coverage, and evidence precision/count.
- Ensure helpers are reusable by unit and integration tests.
- Out of scope: generating scorecard artifacts or baseline comparisons.

## Inputs / Dependencies
- ST-005 quality gate dimensions and terminology.
- Existing test utility patterns in backend tests.

## Implementation Notes
- Keep threshold names stable and dimension-aligned to avoid ambiguous mapping.
- Separate threshold definition from assertion implementation for maintainability.
- Treat threshold changes as explicit rubric-version updates.

## Acceptance Criteria
1. All parity dimensions are represented in centralized threshold constants.
2. Helper assertions cover pass/fail behavior for each dimension.
3. Unit and integration checks consume the same threshold source.
4. No production runtime code path is changed by this task.

## Validation
- Run unit tests for threshold constants and assertion helper behavior.
- Run integration checks proving shared helper usage across test layers.

## Deliverables
- Centralized rubric threshold constants.
- Reusable parity assertion helper module(s).
- Tests demonstrating consistent threshold enforcement.
