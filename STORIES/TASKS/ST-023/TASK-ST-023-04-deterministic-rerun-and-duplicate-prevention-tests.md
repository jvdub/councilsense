# Deterministic Rerun and Duplicate Prevention Tests

**Task ID:** TASK-ST-023-04  
**Story:** ST-023  
**Bucket:** tests  
**Requirement Links:** ST-023 Acceptance Criteria #3 and #5, AGENDA_PLAN §6

## Objective
Add focused unit/integration tests that prove deterministic reruns and duplicate prevention for bundle planning and source-scoped ingestion.

## Scope
- Add unit tests for planner determinism and idempotency key/dedupe branch behavior.
- Add integration tests for repeated ingest windows with unchanged source payloads.
- Add assertions for no duplicate documents/artifacts/publications across reruns.
- Out of scope: broad performance benchmarking and unrelated frontend test additions.

## Inputs / Dependencies
- TASK-ST-023-01 planner deterministic outputs.
- TASK-ST-023-02 source-scoped dedupe behavior.
- TASK-ST-023-03 bundle state transitions.

## Implementation Notes
- Prefer fixed fixtures with explicit checksums and timestamps to avoid flaky assertions.
- Include at least one concurrency-adjacent rerun scenario.
- Keep tests narrow to ST-023 behavior boundaries.

## Acceptance Criteria
1. Test suite covers planner determinism and source-scoped dedupe behavior. (ST-023 AC #5)
2. Rerun integration tests confirm no duplicate records/publications in same ingest window. (ST-023 AC #3)
3. Failures emit diagnostics that identify bundle/source causing duplicate risk. (supports operations)

## Validation
- Run targeted backend unit and integration test subsets.
- Verify tests fail on intentionally broken dedupe path and pass on corrected path.
- Document fixture assumptions for replay reproducibility.

## Deliverables
- New/updated deterministic rerun test modules.
- Duplicate-prevention integration fixtures.
- Test evidence summary for ST-023 acceptance checks.
