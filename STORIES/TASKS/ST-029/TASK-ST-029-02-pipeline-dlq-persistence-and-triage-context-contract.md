# Pipeline DLQ Persistence and Triage Context Contract

**Task ID:** TASK-ST-029-02  
**Story:** ST-029  
**Bucket:** data  
**Requirement Links:** ST-029 Acceptance Criteria #2 and #5, AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 4, AGENDA_PLAN §7 Observability

## Objective
Implement pipeline DLQ data persistence and triage context capture for terminal failures with complete metadata required for safe replay and operational diagnosis.

## Scope
- Define and implement DLQ entities/fields for terminal pipeline failures.
- Persist stage/source/run identifiers, failure class, payload references, and triage metadata.
- Define DLQ state transitions needed for triage and replay readiness.
- Out of scope: replay execution command flow and idempotent stage re-execution guards.

## Inputs / Dependencies
- TASK-ST-029-01 retry classification contract and terminal failure outputs.
- Existing pipeline persistence model and migration conventions.
- Observability field requirements from AGENDA_PLAN §7.

## Implementation Notes
- Keep DLQ schema additive and compatible with current pipeline history tracking.
- Capture fields needed for deterministic replay targeting and audit linkage.
- Ensure terminal-failure inserts are idempotent at retry-cap boundary.

## Acceptance Criteria
1. Terminal failures route to pipeline DLQ with complete triage context.
2. DLQ records include stage/source/run metadata sufficient for replay targeting.
3. DLQ persistence is stable under repeated terminal events and reruns.
4. DLQ contract is documented for operator and replay workflow consumers.

## Validation
- Execute terminal failure scenarios across multiple stages/sources.
- Verify DLQ records include required metadata fields and status transitions.
- Confirm no duplicate terminal entries beyond defined idempotency semantics.

## Deliverables
- DLQ schema and contract documentation.
- Triage metadata field mapping.
- DLQ routing and persistence verification evidence.
