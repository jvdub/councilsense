# Bundle State Tracking and Source Outcome Wiring

**Task ID:** TASK-ST-023-03  
**Story:** ST-023  
**Bucket:** backend  
**Requirement Links:** ST-023 Scope (source-scoped ingest/extract outcomes), ST-023 Acceptance Criteria #1-#4, AGENDA_PLAN §3 and §5

## Objective
Wire source-level ingest/extract outcomes into bundle-level state tracking so publish continuity reflects complete, partial, and missing-source scenarios deterministically.

## Scope
- Define bundle state model fields and transitions based on per-source outcomes.
- Map source ingest/extract outcomes to bundle readiness and limited-confidence reasons.
- Ensure deterministic rerun behavior for already-completed source states.
- Out of scope: final reader UI changes and non-MVP mismatch heuristics.

## Inputs / Dependencies
- TASK-ST-023-01 planner bundle contract.
- TASK-ST-023-02 dedupe outcomes and source-scoped keys.
- Existing summarize/publish stage interfaces.

## Implementation Notes
- Preserve minutes-authoritative behavior while allowing supplemental source coverage.
- Emit explicit reason codes for missing/failed supplemental sources.
- Keep state transitions idempotent for replay/retry paths.

## Acceptance Criteria
1. Bundle state deterministically represents source completeness and readiness for publish. (ST-023 AC #1)
2. Reruns do not regress or duplicate completed source outcomes. (ST-023 AC #3)
3. Pilot-city flow supports minutes plus at least one supplemental artifact path to publish. (ST-023 AC #4)

## Validation
- Integration tests for full-source, partial-source, and missing-source bundle states.
- Replay tests to confirm idempotent state transitions.
- Verify limited-confidence reason outputs for degraded source coverage.

## Deliverables
- Bundle state transition specification.
- Source outcome wiring implementation.
- Integration coverage for continuity and partial-source behavior.
