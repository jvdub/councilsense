# Add orchestration integration tests

**Task ID:** TASK-ST-004-05  
**Story:** ST-004  
**Bucket:** tests  
**Requirement Links:** FR-3, FR-7(4), NFR-1, NFR-2

## Objective
Verify scheduled orchestration behavior for multi-city processing, lifecycle persistence, and retries.

## Scope
- Add integration tests for per-city enqueue and stage flow.
- Add tests for failure isolation and retryability.
- Add checks for run lifecycle statuses/timestamps.
- Out of scope: load/performance benchmarking.

## Inputs / Dependencies
- TASK-ST-004-03
- TASK-ST-004-04

## Implementation Notes
- Target integration suites around scheduler/workers/run repository.
- Use deterministic fixtures to simulate city-level failures.

## Acceptance Criteria
1. Multi-city runs execute independently in tests.
2. Retry behavior matches transient/permanent policy.
3. Run lifecycle records reflect expected statuses and timestamps.

## Validation
- Run story-specific integration test subset for orchestration pipeline.
- Confirm tests pass with stable results across repeated runs.

## Deliverables
- New/updated integration tests for ST-004 orchestration outcomes.
