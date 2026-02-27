# Implement user bootstrap and onboarding guard

**Task ID:** TASK-ST-001-03  
**Story:** ST-001  
**Bucket:** backend  
**Requirement Links:** FR-2, FR-6, NFR-3

## Objective
Create first-run bootstrap behavior that requires valid `home_city_id` before normal app access.

## Scope
- Add/adjust bootstrap endpoint logic to read/create user profile.
- Enforce onboarding-required state when `home_city_id` is missing.
- Validate selected city against configured city list.
- Out of scope: frontend rendering of onboarding page.

## Inputs / Dependencies
- TASK-ST-001-02
- Configured city registry (current source of truth)

## Implementation Notes
- Target profile service/repository and bootstrap endpoint contract.
- Return explicit state flag for frontend redirect decision.

## Acceptance Criteria
1. First-time authenticated users without city are marked onboarding-required.
2. Returning users with valid `home_city_id` are marked onboarding-complete.
3. Invalid city IDs are rejected with validation error.

## Validation
- Add/update service or API tests for bootstrap states.
- Verify city validation against configured registry only.

## Deliverables
- Updated bootstrap/profile endpoint behavior.
- Validation handling for unsupported city IDs.
