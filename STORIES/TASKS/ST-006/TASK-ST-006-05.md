# Reader API Contract and Pagination Test Coverage

**Task ID:** TASK-ST-006-05  
**Story:** ST-006  
**Bucket:** tests  
**Requirement Links:** MVP §4.5(1-2), FR-2, FR-6, NFR-2

## Objective
Provide end-to-end test coverage for city-scoped reader API correctness, payload contract, and pagination behavior.

## Scope (+ Out of scope)
- Add integration tests for list/detail happy paths.
- Add negative tests for city-scope violations.
- Add pagination tests for list endpoint.
- Out of scope: frontend UI tests.

## Inputs / Dependencies
- TASK-ST-006-02, TASK-ST-006-03, TASK-ST-006-04.
- Stable fixture data with multiple cities and meetings.

## Implementation Notes
- Assert required detail fields: summary, decisions, topics, evidence pointers, confidence.
- Keep tests deterministic with explicit fixture ordering.
- Include at least one `limited_confidence` detail fixture.

## Acceptance Criteria
1. API contract tests enforce required payload fields.
2. Scope enforcement tests prevent cross-city data access.
3. Pagination tests confirm stable traversal.

## Validation
- Run targeted reader API integration test suite.
- Capture and attach passing test output for story evidence.

## Deliverables
- New/updated integration and contract tests.
- Test evidence entry for story DoD.
