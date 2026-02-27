# Add backend auth and session validation middleware

**Task ID:** TASK-ST-001-02  
**Story:** ST-001  
**Bucket:** backend  
**Requirement Links:** FR-1, FR-6, NFR-3

## Objective
Protect profile/bootstrap endpoints with identity validation and user context injection.

## Scope
- Implement/extend auth middleware for token/session validation.
- Attach authenticated user identity to request context.
- Out of scope: onboarding UI, city selection UX.

## Inputs / Dependencies
- TASK-ST-001-01
- Existing API framework middleware pattern

## Implementation Notes
- Target API middleware stack and protected route registration.
- Keep behavior consistent for unauthorized and expired sessions.

## Acceptance Criteria
1. Protected endpoints reject requests without valid auth.
2. Authenticated requests include stable user identity in context.
3. Unauthorized response contract is consistent across endpoints.

## Validation
- Run API integration tests for authorized vs unauthorized access.
- Verify middleware execution on target routes.

## Deliverables
- Middleware implementation updates.
- Route protection wiring for ST-001 endpoints.
