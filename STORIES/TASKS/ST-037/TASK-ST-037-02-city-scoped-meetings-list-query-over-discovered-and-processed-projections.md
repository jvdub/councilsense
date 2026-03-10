# City-Scoped Meetings List Query Over Discovered and Processed Projections

**Task ID:** TASK-ST-037-02  
**Story:** ST-037  
**Bucket:** backend  
**Requirement Links:** ST-037 Acceptance Criteria #1, #2, and #4, FR-6, NFR-2

## Objective

Implement the city-scoped meetings list query that pages through discovered meetings while projecting local processing state when available.

## Scope

- Build a paginated city-scoped list query over discovered meetings plus local processing/publication state.
- Project additive status fields and discovered metadata according to the frozen contract.
- Enforce home-city scoping consistent with existing reader API behavior.
- Out of scope: processing-request endpoint, admission-control enforcement, and frontend tile behavior.

## Inputs / Dependencies

- TASK-ST-037-01 reader API payload design.
- TASK-ST-036-01 discovered-meeting schema.
- Existing city-scoped list query and access-control patterns from ST-006.

## Implementation Notes

- Preserve stable pagination semantics even when mixing discovered-only and processed records.
- Keep projection logic tolerant of meetings with no local processing record yet.
- Reuse city-access-denied behavior from existing reader endpoints.

## Acceptance Criteria

1. City meetings list includes discovered meetings regardless of whether a summary exists. (ST-037 AC #1)
2. Status projection distinguishes discovered-only vs active vs completed work. (ST-037 AC #2)
3. Home-city scoping is enforced identically to existing reader list behavior. (ST-037 AC #4)

## Validation

- Integration tests for mixed discovered/processed pages.
- Query-plan checks for city-scoped pagination and status projection.
- Scope-enforcement tests for unauthorized city access.

## Deliverables

- City-scoped discovered-meeting list query and API wiring.
- Pagination/status projection implementation.
- Integration/query-plan coverage for mixed projection behavior.
