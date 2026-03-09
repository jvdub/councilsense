# Fixture Coverage, Specificity, and Determinism Tests

**Task ID:** TASK-ST-032-05  
**Story:** ST-032  
**Bucket:** tests  
**Requirement Links:** ST-032 Acceptance Criteria #1 through #5, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §14(10-11)

## Objective

Add fixture coverage and scorecard-style checks for structured subject specificity, location carry-through, impact-tag determinism, and low-confidence behavior.

## Scope

- Add tests for full-detail, partial-detail, and generic-source cases.
- Verify deterministic structured extraction and impact-tag ordering across reruns.
- Validate conflict and sparse-evidence fallback behavior.
- Out of scope: reader API and frontend rendering verification.

## Inputs / Dependencies

- TASK-ST-032-04 carry-through and limited-confidence behavior.
- Existing scorecard and fixture patterns from ST-017 through ST-020.

## Implementation Notes

- Reuse existing rubric and fixture infrastructure where practical.
- Keep assertions focused on grounded specificity and determinism rather than prose style alone.
- Capture representative resident-relevance scenarios that are likely in production.

## Acceptance Criteria

1. Fixtures cover concrete subject/location extraction, sparse source detail, and conflicting-source scenarios.
2. Repeated runs produce stable structured relevance outputs and `impact_tags` ordering.
3. Low-confidence cases are asserted explicitly rather than implied by absent fields alone.
4. Tests provide clear failure diagnostics for missing specificity carry-through.

## Validation

- Run targeted resident-relevance test module(s) and existing specificity hardening suites.
- Review failure messages for clear field-level diagnostics.
- Confirm scorecard-style checks remain reproducible for unchanged fixtures.

## Deliverables

- Fixture and test coverage for structured relevance extraction.
- Determinism assertions for `impact_tags` and carry-through behavior.
- Failure diagnostics for specificity regression cases.