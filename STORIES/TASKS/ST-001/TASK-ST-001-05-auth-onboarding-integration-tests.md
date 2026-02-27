# Add auth and onboarding integration coverage

**Task ID:** TASK-ST-001-05  
**Story:** ST-001  
**Bucket:** tests  
**Requirement Links:** FR-1, FR-2, FR-6, NFR-3

## Objective
Verify end-to-end behavior for authentication, onboarding gating, and city validation.

## Scope
- Add integration tests for first-run and returning user behavior.
- Add invalid city case coverage.
- Out of scope: performance/load testing.

## Inputs / Dependencies
- TASK-ST-001-03
- TASK-ST-001-04

## Implementation Notes
- Target API integration test suite and frontend flow tests where present.
- Keep fixtures focused on user identity and city registry variants.

## Acceptance Criteria
1. First-run authenticated user is forced through onboarding path.
2. Returning authenticated user bypasses onboarding.
3. Invalid city update attempt fails with expected error contract.

## Validation
- Run story-specific integration test subset.
- Confirm all new tests pass in CI/local test command.

## Deliverables
- New/updated integration test files for ST-001 scenarios.
