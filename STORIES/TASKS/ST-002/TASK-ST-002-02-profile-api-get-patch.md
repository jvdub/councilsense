# Implement profile read/update endpoints

**Task ID:** TASK-ST-002-02  
**Story:** ST-002  
**Bucket:** backend  
**Requirement Links:** FR-2, FR-6, NFR-3

## Objective
Provide authenticated `GET /v1/me` and `PATCH /v1/me` endpoints with strict request validation.

## Scope
- Implement response model for profile read.
- Implement patch semantics for city and notification fields.
- Validate city IDs and pause window payload shape.
- Out of scope: frontend settings screen.

## Inputs / Dependencies
- TASK-ST-002-01
- Auth/session context from ST-001

## Implementation Notes
- Target API route handlers, schemas, and profile service.
- Keep response fields stable (`email`, `home_city_id`, notification settings).

## Acceptance Criteria
1. `GET /v1/me` returns current authenticated user profile state.
2. `PATCH /v1/me` persists allowed fields and rejects invalid payloads.
3. City updates accept only configured city IDs.

## Validation
- Run API tests for happy path and validation failures.
- Verify DB state changes only for targeted user record.

## Deliverables
- Endpoint handlers and request/response schema updates.
