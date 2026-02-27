# Persist run lifecycle and stage outcomes

**Task ID:** TASK-ST-004-03  
**Story:** ST-004  
**Bucket:** data  
**Requirement Links:** FR-7(4), NFR-2, NFR-5

## Objective
Record processing run lifecycle with statuses and timestamps for operations/debugging visibility.

## Scope
- Persist `pending`, `processed`, `failed`, `limited_confidence` states.
- Persist `started_at` and `finished_at` timestamps.
- Capture stage outcome metadata linked to run/city context.
- Out of scope: alerting/dashboard presentation.

## Inputs / Dependencies
- TASK-ST-004-02
- Existing run/meeting persistence patterns

## Implementation Notes
- Target run-status schema/model plus worker update hooks.
- Keep updates atomic enough to avoid inconsistent final states.

## Acceptance Criteria
1. Every run has lifecycle status transitions persisted.
2. Start and finish timestamps are recorded when applicable.
3. Stage outcomes are queryable by run/city identifiers.

## Validation
- Run repository/service tests for status transition writes.
- Execute integration path verifying run records from enqueue to completion/failure.

## Deliverables
- Schema/model updates and lifecycle persistence implementation.
