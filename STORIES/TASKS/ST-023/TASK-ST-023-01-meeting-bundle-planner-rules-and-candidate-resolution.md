# Meeting Bundle Planner Rules and Candidate Resolution

**Task ID:** TASK-ST-023-01  
**Story:** ST-023  
**Bucket:** backend  
**Requirement Links:** ST-023 Scope (bundle planning), ST-023 Acceptance Criteria #1, AGENDA_PLAN §3

## Objective

Define and implement deterministic meeting bundle planning that resolves expected source types (minutes, agenda, packet) per eligible meeting candidate.

## Scope

- Specify planner inputs, ordering, and tie-break rules for meeting candidate resolution.
- Define expected-source resolution rules by city/source configuration.
- Produce bundle identity contract used by downstream ingestion stages.
- Out of scope: source extraction internals, dedupe persistence behavior, and publish-path changes.

## Inputs / Dependencies

- ST-003 city/source configuration contracts.
- ST-004 scheduled ingestion orchestration behavior.
- ST-022 idempotency/stage contract assumptions.

## Implementation Notes

- Planner must produce stable output order for identical input windows.
- Include explicit handling for missing source registrations.
- Record planner diagnostics for skipped/invalid candidates.

## Acceptance Criteria

1. Deterministic bundle planner outputs one bundle per eligible meeting candidate with stable source expectations. (ST-023 AC #1)
2. Output remains stable across reruns of the same ingest window and config snapshot. (ST-023 AC #1)
3. Planner diagnostics identify why candidates are skipped or partially scoped. (supports operations)

## Validation

- Unit tests for ordering/tie-break behavior and source expectation resolution.
- Regression fixture replay to verify stable bundle identity across reruns.
- Peer review planner rules against pilot-city source configuration.

## Deliverables

- Bundle planner contract and implementation notes.
- Candidate/source expectation rule table.
- Determinism-focused unit test coverage.
