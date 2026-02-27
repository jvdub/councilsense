# Manual Review State and Reader Flag

**Task ID:** TASK-ST-010-04  
**Story:** ST-010  
**Bucket:** backend  
**Requirement Links:** FR-7, NFR-4

## Objective
Apply confidence threshold policy to route low-confidence outputs to manual_review_needed and expose limited-confidence reader flag.

## Scope
- In scope:
  - Confidence evaluation in processing result pipeline.
  - State transition to manual_review_needed.
  - Reader-visible low-confidence indicator in meeting payload.
- Out of scope:
  - Full reviewer workflow tooling.

## Inputs / Dependencies
- TASK-ST-010-01
- ST-005 extraction output

## Implementation Notes
- Confidence evaluation happens once per run using persisted score.
- Include explicit fallback behavior when score is absent.
- Keep API response backward-compatible.

## Acceptance Criteria
1. Low-confidence runs are flagged manual_review_needed.
2. Non-low-confidence runs are not incorrectly flagged.
3. Reader response includes limited-confidence indicator when applicable.

## Validation
- Run integration tests at below-threshold, at-threshold, and above-threshold values.
- Run API contract test for reader confidence indicator field.

## Deliverables
- Processing-state transition logic updates.
- Reader response model updates.
- Threshold transition and API contract tests.
