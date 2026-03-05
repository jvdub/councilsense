# Flag-State Contract and Integration Test Matrix

**Task ID:** TASK-ST-027-04  
**Story:** ST-027  
**Bucket:** tests  
**Requirement Links:** ST-027 Acceptance Criteria #1, #2, #3, #4, AGENDA_PLAN §6 Testing and validation plan

## Objective

Add contract and integration coverage that proves baseline parity in flag-off mode and additive payload correctness in flag-on mode.

## Scope

- Add API contract fixture matrix for flag-off and flag-on responses.
- Add integration tests for additive field population, omission, and mismatch cases.
- Add regression checks that detect baseline contract drift in flag-off mode.
- Out of scope: performance profiling and production telemetry dashboards.

## Inputs / Dependencies

- TASK-ST-027-03 serializer additive implementation.
- Existing ST-006 reader API contract fixtures.

## Implementation Notes

- Keep baseline fixture snapshots authoritative for flag-off parity.
- Ensure test matrix covers presence/absence permutations for evidence v2 fields.
- Include deterministic ordering assertions where additive arrays are exposed.

## Acceptance Criteria

1. Contract tests validate flag-off baseline parity with existing meeting detail/list semantics.
2. Contract tests validate flag-on additive `planned`, `outcomes`, and mismatch payloads.
3. Tests verify safe omission behavior when evidence v2 data is unavailable.
4. Integration suite catches additive field regressions without affecting baseline clients.

## Validation

- Run targeted API contract test matrix for both flag states.
- Execute integration tests on representative full-source and partial-source fixtures.
- Confirm failure on any baseline parity drift in flag-off mode.

## Deliverables

- Flag-state contract test matrix and fixtures.
- Integration test coverage for additive payload scenarios.
- Regression evidence for baseline parity guarantees.
