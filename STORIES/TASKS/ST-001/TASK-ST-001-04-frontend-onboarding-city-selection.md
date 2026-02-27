# Build onboarding city selection flow

**Task ID:** TASK-ST-001-04  
**Story:** ST-001  
**Bucket:** frontend  
**Requirement Links:** FR-2, FR-6

## Objective
Redirect first-run users to onboarding and persist selected valid home city.

## Scope
- Add first-run redirect based on bootstrap state.
- Build city selector submit flow for onboarding.
- Handle submit success and transition to normal app path.
- Out of scope: auth provider setup and backend token validation.

## Inputs / Dependencies
- TASK-ST-001-03
- Existing app routing/auth state primitives

## Implementation Notes
- Target app route guard/state management and onboarding view components.
- Use backend-provided city list/validation responses.

## Acceptance Criteria
1. Users without `home_city_id` are redirected to onboarding.
2. Valid city submission completes onboarding and exits onboarding route.
3. Returning users with city bypass onboarding.

## Validation
- Run frontend unit/integration checks for route guard behavior.
- Perform manual flow check: first-run, returning user, invalid city submit.

## Deliverables
- Onboarding UI/components and route guard updates.
- Client-side submit/error handling for city selection.
