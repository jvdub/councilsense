# Home-City Scoping Enforcement

**Task ID:** TASK-ST-006-04  
**Story:** ST-006  
**Bucket:** backend  
**Requirement Links:** FR-2, FR-6, MVP §4.5(1-2)

## Objective
Enforce consistent home-city scoping policy for both list and detail reader endpoints.

## Scope (+ Out of scope)
- Add/standardize policy checks for authenticated profile city scope.
- Apply policy to city list and meeting detail access paths.
- Normalize unauthorized access response behavior.
- Out of scope: frontend error messaging.

## Inputs / Dependencies
- TASK-ST-006-02, TASK-ST-006-03.
- Profile/home-city data from ST-002.

## Implementation Notes
- Prevent ID-based cross-city leakage via detail endpoint.
- Prefer centralized policy utility/middleware to avoid drift.
- Keep behavior auditable in logs/metrics where available.

## Acceptance Criteria
1. Users cannot list or fetch meetings outside their home city scope.
2. Both endpoints enforce the same policy semantics.
3. Policy behavior is covered by automated tests.

## Validation
- Run integration tests for cross-city access denial on both endpoints.
- Verify no city leakage in error responses.

## Deliverables
- Shared scoping policy implementation and endpoint wiring.
- Security-focused integration tests.
