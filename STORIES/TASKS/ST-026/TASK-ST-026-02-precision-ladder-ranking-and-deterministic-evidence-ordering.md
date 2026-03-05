# Precision Ladder Ranking and Deterministic Evidence Ordering

**Task ID:** TASK-ST-026-02  
**Story:** ST-026  
**Bucket:** backend  
**Requirement Links:** ST-026 Acceptance Criteria #2, #3, AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision

## Objective

Implement precision ladder ranking and deterministic ordering rules so evidence references are stable across reruns for identical source inputs.

## Scope

- Implement precision rank policy: offset > span > section > file.
- Implement deterministic tie-breakers for equal-precision evidence references.
- Ensure ordering stability across repeated runs with unchanged inputs.
- Out of scope: API projection shape changes and scorecard/reporting visualization.

## Inputs / Dependencies

- TASK-ST-026-01 linkage contract and precision metadata fields.
- Existing summarization claim evidence assembly flow.

## Implementation Notes

- Keep ranking and sorting deterministic by explicit comparator chain, not insertion order.
- Ensure tie-breakers rely on stable identifiers/paths rather than runtime timestamps.
- Preserve all valid references; this task orders and prioritizes, it does not suppress grounded evidence.

## Acceptance Criteria

1. Precision ladder follows offset > span > section > file ordering.
2. Equal-precision references have deterministic tie-break behavior.
3. Identical reruns produce identical evidence ordering.
4. References with parser precision metadata preferentially rank above file-level references.

## Validation

- Run deterministic rerun tests using fixed fixtures and compare sorted evidence outputs.
- Validate mixed-precision inputs to confirm rank ordering and tie-break stability.
- Confirm no non-deterministic ordering under parallelized pipeline execution.

## Deliverables

- Precision ranking and deterministic comparator contract.
- Fixture-backed rerun stability assertions for sorted evidence references.
- Documentation of tie-break order for equal-precision references.
