# Meetings Page Pagination and API Contract

**Task ID:** TASK-ST-039-01  
**Story:** ST-039  
**Bucket:** frontend  
**Requirement Links:** ST-039 Acceptance Criteria #1 and #4, FR-4, FR-6, NFR-2

## Objective

Adapt the meetings page data model to the discovered-meetings API so the page can paginate through source meetings while preserving existing detail navigation for processed meetings.

## Scope

- Update frontend list models and API client assumptions for discovered-meeting pagination.
- Define page state and query-param handling for the expanded list contract.
- Preserve compatibility with processed meeting detail navigation.
- Out of scope: tile variants, request-processing actions, and user messaging.

## Inputs / Dependencies

- TASK-ST-037-01 additive reader API contract.
- Existing `/meetings` page pagination and deep-link patterns from ST-007.

## Implementation Notes

- Keep the data model additive so a staged rollout can preserve the old path behind a flag if needed.
- Normalize new processing states centrally before rendering tiles.
- Avoid introducing client-only pagination state that cannot survive refresh/navigation.

## Acceptance Criteria

1. Meetings page can consume paginated discovered-meeting data. (ST-039 AC #1)
2. Processed meetings still resolve cleanly to meeting detail navigation. (ST-039 AC #4)
3. Pagination state remains durable across navigation and refresh.

## Validation

- Component/page tests for paginated list loading with discovered-meeting payloads.
- Verify processed meeting items still produce valid detail links.
- Confirm URL/query-param behavior remains stable across reloads.

## Deliverables

- Updated meetings page data model and API client integration.
- Pagination/query-param state contract for the meeting explorer.
- Test coverage for discovered-meeting page loading behavior.
