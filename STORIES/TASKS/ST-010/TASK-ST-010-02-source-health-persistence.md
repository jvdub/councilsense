# Source Health Persistence

**Task ID:** TASK-ST-010-02  
**Story:** ST-010  
**Bucket:** data  
**Requirement Links:** FR-7, NFR-4

## Objective
Persist and update source health_status and last_success_at during ingest attempts.

## Scope
- In scope:
  - Schema updates for source health fields.
  - Ingest attempt hooks to update status and timestamps.
  - Failure isolation at source granularity.
- Out of scope:
  - Dashboard visuals.

## Inputs / Dependencies
- TASK-ST-010-01
- ST-004 ingestion orchestration hooks

## Implementation Notes
- Update health based on attempt outcome, not only run finalization.
- Preserve previous failure context for triage.
- Avoid cross-source cascading state updates.

## Acceptance Criteria
1. Every ingest attempt updates source health state deterministically.
2. Successful attempts update last_success_at.
3. Failed source attempts do not block unrelated source processing.

## Validation
- Run integration tests for success-to-failure and failure-to-success transitions.
- Run test proving unrelated source continues processing on single-source failure.

## Deliverables
- Migration and model changes.
- Ingest pipeline updates for health writes.
- Integration tests for source-level isolation.
