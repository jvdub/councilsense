# Build settings editor for profile preferences

**Task ID:** TASK-ST-002-04  
**Story:** ST-002  
**Bucket:** frontend  
**Requirement Links:** FR-2, FR-5(4)

## Objective
Allow authenticated users to view and edit home city and notification preferences from settings UI.

## Scope
- Render current profile preference values from `GET /v1/me`.
- Submit updates via `PATCH /v1/me` for city and notification fields.
- Include pause/unpause control interaction.
- Out of scope: onboarding-first-run route logic (ST-001).

## Inputs / Dependencies
- TASK-ST-002-02
- TASK-ST-002-03

## Implementation Notes
- Target settings route/components and API client bindings.
- Keep form state and server validation error handling concise.

## Acceptance Criteria
1. Settings page shows current persisted values.
2. User can update city and notification settings successfully.
3. Pause set/remove action reflects in refreshed state.

## Validation
- Run frontend tests for form load, submit, and error handling.
- Perform manual smoke check for save + reload consistency.

## Deliverables
- Settings UI updates and client integration for profile endpoints.
