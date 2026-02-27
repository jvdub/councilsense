# Operator View and Transition Tests

**Task ID:** TASK-ST-010-05  
**Story:** ST-010  
**Bucket:** ops  
**Requirement Links:** FR-7, NFR-4

## Objective
Provide a minimal operator-facing query/view and validation tests for stale, failing, and manual-review candidate sources/runs.

## Scope
- In scope:
  - Basic operator query endpoint or admin query script.
  - Filters for stale sources, failing sources, manual_review_needed runs.
  - Consolidated transition coverage tests.
- Out of scope:
  - Advanced dashboarding and alert automation.

## Inputs / Dependencies
- TASK-ST-010-02
- TASK-ST-010-03
- TASK-ST-010-04

## Implementation Notes
- Keep output machine-readable and triage-friendly.
- Include timestamps and version provenance in operator output.
- Ensure view works without blocking active pipeline operations.

## Acceptance Criteria
1. Operator can list stale/failing sources quickly.
2. Operator can list manual-review-needed runs with provenance metadata.
3. Automated tests cover expected transition pathways.

## Validation
- Run end-to-end test generating one stale source and one manual-review run.
- Run query output snapshot test for required fields.

## Deliverables
- Operator query/view implementation.
- Transition and output tests.
- Short triage usage note for operations.
