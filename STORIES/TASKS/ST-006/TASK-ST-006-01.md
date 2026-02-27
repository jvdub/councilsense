# Reader Query Index and Contract Prep

**Task ID:** TASK-ST-006-01  
**Story:** ST-006  
**Bucket:** data  
**Requirement Links:** MVP §4.5(1-2), FR-6, NFR-2

## Objective
Prepare efficient city-scoped meeting list query paths and pagination-ready ordering contract.

## Scope (+ Out of scope)
- Add/verify indexes for city/date/status filters used by list endpoint.
- Define canonical sort and cursor/page contract for meeting list retrieval.
- Out of scope: HTTP route implementation.

## Inputs / Dependencies
- Existing meeting storage schema.
- ST-005 status/confidence fields.

## Implementation Notes
- Keep default ordering stable for pagination consistency.
- Include confidence/status fields in read model projection.
- Prefer additive index changes only.

## Acceptance Criteria
1. City/date list query path is indexed for expected MVP dataset sizes.
2. Pagination contract is deterministic across repeated requests.
3. Query returns fields needed by list API without extra joins where possible.

## Validation
- Run explain/query-plan checks on list query.
- Run targeted DB-access tests for list retrieval.

## Deliverables
- Index/migration updates and query contract notes.
