# City-Scoped Meetings List Endpoint

**Task ID:** TASK-ST-006-02  
**Story:** ST-006  
**Bucket:** backend  
**Requirement Links:** MVP §4.5(1), FR-2, FR-6, NFR-2

## Objective
Implement GET city meetings list endpoint with authenticated access and pagination.

## Scope (+ Out of scope)
- Implement GET /v1/cities/{city_id}/meetings.
- Return paginated meetings list for user-authorized city scope.
- Include status/confidence labels required for frontend list rendering.
- Out of scope: meeting detail payload.

## Inputs / Dependencies
- TASK-ST-006-01.
- Authenticated user profile with home city.
- Story dependency: ST-002 auth/profile.

## Implementation Notes
- Keep endpoint read-only and idempotent.
- Validate pagination params and defaults.
- Ensure city path param cannot bypass policy checks.

## Acceptance Criteria
1. Authenticated users can fetch meetings list for authorized city.
2. Response includes pagination metadata and confidence/status fields.
3. Unauthorized city access is rejected.

## Validation
- Run API integration tests for list success and unauthorized city attempts.
- Verify pagination behavior across multiple pages.

## Deliverables
- Endpoint handler/service code and API contract tests.
