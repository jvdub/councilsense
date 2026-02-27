# Meetings List Page

**Task ID:** TASK-ST-007-02  
**Story:** ST-007  
**Bucket:** frontend  
**Requirement Links:** MVP §4.5(1), NFR-2

## Objective
Implement `/meetings` page showing recent meetings for the user’s city with robust loading, empty, and error handling.

## Scope (+ Out of scope)
- Render list of meetings from reader list API.
- Add pagination/incremental loading interaction.
- Implement explicit loading, empty, and error states.
- Out of scope: meeting detail sections.

## Inputs / Dependencies
- TASK-ST-007-01.
- ST-006 list endpoint availability.

## Implementation Notes
- Keep city scope implicit via authenticated API responses.
- Show confidence/status labels in list row metadata.
- Preserve navigation continuity when paginating.

## Acceptance Criteria
1. Meetings list renders recent city meetings.
2. Loading/empty/error states are visible and non-breaking.
3. Pagination allows user to access additional pages/items.

## Validation
- Run component tests covering list state permutations.
- Perform manual smoke check for pagination flow.

## Deliverables
- `/meetings` route/page and supporting state components.
- Tests for list states and pagination interaction.
