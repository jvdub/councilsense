# Integration Tests for Discovery Reruns and Provider Parsing

**Task ID:** TASK-ST-036-05  
**Story:** ST-036  
**Bucket:** tests  
**Requirement Links:** ST-036 Acceptance Criteria #1 through #5, FR-3, FR-7, NFR-4

## Objective

Lock in discovery behavior with integration tests that cover provider parsing, sync reruns, dedupe, and local-meeting reconciliation.

## Scope

- Add end-to-end discovery tests for pilot provider enumeration through persistence.
- Verify rerun stability, metadata refresh, and local-meeting reconciliation outcomes.
- Cover failure and sparse-data cases that should still preserve stable identity behavior.
- Out of scope: reader API payload contract and frontend rendering.

## Inputs / Dependencies

- TASK-ST-036-02 provider enumeration.
- TASK-ST-036-04 discovery dedupe behavior.
- Existing test fixtures for pilot-city source data where reusable.

## Implementation Notes

- Prefer deterministic provider fixtures over live source calls.
- Assert both persisted state and linkage semantics.
- Keep tests focused on the discovered-meetings lifecycle, not later queue behavior.

## Acceptance Criteria

1. Integration tests validate first-sync, rerun, and metadata-refresh behavior. (ST-036 AC #2)
2. Provider parsing tests validate stable source identity and normalized metadata. (ST-036 AC #3 and #5)
3. Reconciliation coverage verifies discovered-to-local linkage when a stable match exists. (ST-036 AC #4)

## Validation

- `pytest -q`
- Focused backend test selection for discovery sync and provider parsing paths.

## Deliverables

- Integration test suite for discovery sync lifecycle.
- Deterministic provider fixtures for pilot enumeration coverage.
- Regression assertions for rerun stability and reconciliation.
