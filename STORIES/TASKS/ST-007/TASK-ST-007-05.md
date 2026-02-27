# ST-007 Reader UX Smoke Coverage

**Task ID:** TASK-ST-007-05  
**Story:** ST-007  
**Bucket:** tests  
**Requirement Links:** MVP §4.5(1-3), FR-4, NFR-2

## Objective
Add focused automated coverage for list/detail/deep-link user-critical flows.

## Scope (+ Out of scope)
- Add component/integration tests for list and detail core states.
- Add deep-link smoke test for `meeting_id` navigation.
- Include limited-confidence UI assertion.
- Out of scope: non-reader settings and notifications UI tests.

## Inputs / Dependencies
- TASK-ST-007-02, TASK-ST-007-03, TASK-ST-007-04.
- Stable frontend test fixtures/mocks for reader API.

## Implementation Notes
- Prioritize stable smoke assertions over brittle snapshot breadth.
- Cover loading, empty, error, and happy-path transitions.
- Verify confidence label rendering from API status field.

## Acceptance Criteria
1. Automated tests cover list, detail, limited-confidence, and deep-link flows.
2. Failures clearly indicate which user flow regressed.
3. Test suite can run in CI without external network dependency.

## Validation
- Run targeted frontend test command for meetings reader flows.
- Capture test run output for acceptance evidence.

## Deliverables
- Added/updated frontend tests and fixture data.
- Story-level validation note with executed checks.
