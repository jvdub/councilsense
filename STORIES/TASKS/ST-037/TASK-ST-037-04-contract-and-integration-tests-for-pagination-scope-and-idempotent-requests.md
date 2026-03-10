# Contract and Integration Tests for Pagination, Scope, and Idempotent Requests

**Task ID:** TASK-ST-037-04  
**Story:** ST-037  
**Bucket:** tests  
**Requirement Links:** ST-037 Acceptance Criteria #1 through #5, FR-4, FR-6, NFR-2

## Objective

Protect the expanded reader contract with tests that cover discovered-meeting pagination, status projection, city scoping, and queue-or-return request behavior.

## Scope

- Add contract fixtures for discovered, queued, processing, processed, and failed states.
- Add API integration coverage for list pagination and processing-request idempotency.
- Cover home-city scoping and invalid-request behaviors.
- Out of scope: frontend rendering, admission-control limit semantics, and operator replay behavior.

## Inputs / Dependencies

- TASK-ST-037-02 city-scoped list query.
- TASK-ST-037-03 processing-request endpoint.
- Existing meetings API contract test patterns from ST-006 and later additive stories.

## Implementation Notes

- Favor stable fixtures that downstream frontend tests can reuse.
- Assert both payload shape and idempotent behavioral semantics.
- Keep admission-control assertions out of this task so ST-038 can extend them cleanly.

## Acceptance Criteria

1. Contract tests validate mixed discovered/processed list pagination. (ST-037 AC #1)
2. Integration tests validate status projection and scope enforcement. (ST-037 AC #2 and #4)
3. Request tests validate create-vs-return-existing behavior for repeated active requests. (ST-037 AC #3 and #5)

## Validation

- `pytest -q`
- Focused backend test selection for meetings API contract and request endpoint behavior.

## Deliverables

- Contract fixtures for discovered-meeting and request outcomes.
- API integration tests for pagination, scoping, and idempotency.
- Regression coverage for additive reader-contract changes.
