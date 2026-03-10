# Retry Policy Matrix and Bounded Attempts by Stage/Source

**Task ID:** TASK-ST-029-01  
**Story:** ST-029  
**Bucket:** backend  
**Requirement Links:** ST-029 Acceptance Criteria #1 and #5, AGENDA_PLAN §5 Phase 4, AGENDA_PLAN §6 Testing and validation plan

## Objective

Define and implement source-aware retry classification rules with bounded retry attempts for each pipeline stage and source type.

## Scope

- Define transient vs terminal failure classes per stage/source combination.
- Define retry cap policy and attempt accounting semantics.
- Implement policy resolution contract consumed by execution workers.
- Out of scope: DLQ persistence schema and replay command/audit flow.

## Inputs / Dependencies

- ST-014 failure handling baselines and retry hardening context.
- ST-023 source-scoped ingestion/stage boundaries.
- Existing pipeline stage execution and failure taxonomy.

## Implementation Notes

- Keep policy deterministic and explicitly versioned for operator traceability.
- Ensure attempt counters are monotonic and safe across reruns/restarts.
- Make terminal classification explicit to support DLQ routing decisions.

## Acceptance Criteria

1. Retry policy matrix distinguishes transient and terminal classes by stage/source.
2. Bounded retry caps are enforced consistently for all matrix entries.
3. Retry classification outputs are machine-readable for downstream DLQ logic.
4. Classification and cap behavior are covered by unit/integration verification plans.

## Validation

- Run classification matrix scenarios across representative stage/source failures.
- Verify attempt counters and cap behavior across reruns.
- Confirm terminal classifications are emitted for DLQ routing handoff.

## Deliverables

- Retry classification matrix specification.
- Bounded-attempt policy contract.
- Verification matrix for transient/terminal outcomes.
