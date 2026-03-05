# Idempotent Replay Guards and Publication Side-Effect Protection

**Task ID:** TASK-ST-029-04  
**Story:** ST-029  
**Bucket:** backend  
**Requirement Links:** ST-029 Acceptance Criteria #4 and #5, AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 4

## Objective
Implement idempotent replay guards in stage execution so replayed work does not produce duplicate publications or duplicate downstream artifacts.

## Scope
- Add replay idempotency guard checks before stage side effects.
- Define no-op behavior when replay target has already produced terminal outputs.
- Protect publication/artifact writes against duplicate creation on replay.
- Out of scope: retry policy matrix definition and operator command UX.

## Inputs / Dependencies
- TASK-ST-029-01 retry classification and cap semantics.
- TASK-ST-029-03 replay command flow and audit metadata.
- Existing publication transaction and dedupe key patterns.

## Implementation Notes
- Prefer deterministic dedupe keys derived from city/meeting/stage/source/run scope.
- Record explicit no-op outcomes in audit trail when guard short-circuits replay.
- Ensure guard behavior is safe under concurrent replay attempts.

## Acceptance Criteria
1. Replay execution path enforces idempotent guards for side-effecting stages.
2. Replaying already-completed work yields deterministic no-op outcomes.
3. Duplicate publications/artifacts are prevented for replayed terminal failures.
4. Guard outcomes are visible in replay audit records and diagnostics.

## Validation
- Run replay scenarios for already-processed, partially-processed, and failed states.
- Verify no duplicate publication/artifact records across repeated replay attempts.
- Confirm no-op outcomes are persisted and surfaced for operators.

## Deliverables
- Stage replay idempotency guard contract.
- Publication/artifact duplicate-prevention verification notes.
- Replay no-op behavior evidence.
