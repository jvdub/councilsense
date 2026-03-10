# Replay Command Flow with Actor/Reason and Audit History

**Task ID:** TASK-ST-029-03  
**Story:** ST-029  
**Bucket:** backend  
**Requirement Links:** ST-029 Acceptance Criteria #3 and #5, AGENDA_PLAN §5 Phase 4, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective

Implement operator replay command flow that requires actor and reason metadata and persists full replay audit history.

## Scope

- Define replay request contract requiring actor and reason fields.
- Implement replay action recording with idempotency key and replay outcome metadata.
- Link replay actions to DLQ records and pipeline run context.
- Out of scope: stage-level idempotent execution guards and duplicate publication prevention internals.

## Inputs / Dependencies

- TASK-ST-029-02 DLQ persistence and triage context model.
- Existing operator tooling surfaces and authorization patterns.
- Runbook and audit requirements from AGENDA_PLAN §7.

## Implementation Notes

- Reject replay requests that omit actor/reason metadata.
- Persist replay intent and replay result events for full operator traceability.
- Make audit records queryable by city/meeting/run/stage and actor.

## Acceptance Criteria

1. Replay actions require actor and reason metadata at command initiation.
2. Replay actions persist audit history including idempotency key and result state.
3. Replay history links deterministically to corresponding DLQ entries.
4. Replay audit records support operational triage and compliance review.

## Validation

- Execute replay command scenarios with valid/invalid metadata payloads.
- Verify audit record creation for replay start, success, no-op, and failure outcomes.
- Confirm queryability of replay history by core operational dimensions.

## Deliverables

- Replay command contract and validation rules.
- Replay audit history schema/field mapping.
- Operator replay workflow verification evidence.
