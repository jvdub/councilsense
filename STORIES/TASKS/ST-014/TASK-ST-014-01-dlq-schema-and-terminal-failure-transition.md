# DLQ Schema and Terminal Failure Transition

**Task ID:** TASK-ST-014-01  
**Story:** ST-014  
**Bucket:** data  
**Requirement Links:** FR-5, NFR-4

## Objective
Add DLQ persistence and deterministic transition of exhausted notification attempts into DLQ state.

## Scope
- Define DLQ entity/table and linkage to notification attempts.
- Implement terminal transition logic from retry-exhausted to DLQ.
- Store failure reason and transition timestamp.
- Out of scope: replay actions and dashboarding.

## Inputs / Dependencies
- Existing notification attempt model and retry handling path.
- ST-009 idempotent fanout contract.

## Implementation Notes
- Keep original notification identifier for replay traceability.
- Persist final failure classification (transient/permanent/unknown).
- Ensure transition is single-write and idempotent.

## Acceptance Criteria
1. Exhausted attempts always end in DLQ state.
2. DLQ record includes reason, source identifiers, and terminal timestamp.
3. Duplicate terminal transitions do not create duplicate DLQ entries.
4. DLQ records are queryable by city/source/run/message identifiers.

## Validation
- Integration test for retry exhaustion -> DLQ transition.
- Idempotency test for repeated terminal transition calls.
- Query test for operational filters.

## Deliverables
- Migration and DLQ model updates.
- Transition logic in notification processing path.
- Tests for transition correctness and idempotency.
