# Meeting Reader API (City List + Detail)

**Story ID:** ST-006  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.5(1-2), FR-2, FR-6, NFR-2

## User Story
As a resident, I want to browse meetings for my city and open details with evidence so I can quickly understand what happened.

## Scope
- Build reader endpoints for city-scoped meeting list and meeting detail.
- Enforce access and city-scoping based on user profile home city.
- Include summary, decisions, topics, and evidence pointers in detail payload.

## Acceptance Criteria
1. Authenticated user can fetch meetings list scoped to their city.
2. Detail response includes summary, key decisions, notable topics, and evidence pointers.
3. Meeting status and confidence labels are included for UI rendering.
4. Reader endpoints are read-only (`GET`) and enforce city scoping from authenticated user profile.
5. Pagination works for normal dataset sizes.

## Implementation Tasks
- [ ] Implement `GET /v1/cities/{city_id}/meetings` with pagination.
- [ ] Implement `GET /v1/meetings/{meeting_id}` and evidence payload linkage.
- [ ] Enforce city scoping policy from authenticated user profile.
- [ ] Add query/index tuning for city/date list access patterns.
- [ ] Add integration tests for scope enforcement and payload shape.

## Dependencies
- ST-002
- ST-005

## Definition of Done
- Reader APIs serve complete meeting data for home city with required fields.
- Access policy and payload contract are validated by automated tests.
- API supports frontend performance target efforts for meetings page.
