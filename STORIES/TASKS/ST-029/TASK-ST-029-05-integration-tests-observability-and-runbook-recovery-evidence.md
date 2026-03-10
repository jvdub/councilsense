# Integration Tests, Observability, and Runbook Recovery Evidence

**Task ID:** TASK-ST-029-05  
**Story:** ST-029  
**Bucket:** ops  
**Requirement Links:** ST-029 Acceptance Criteria #5, AGENDA_PLAN §5 Phase 4, AGENDA_PLAN §6 Testing and validation plan, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective

Deliver integration verification and operational evidence for retry caps, DLQ routing, replay auditability, and idempotent no-duplicate recovery behavior.

## Scope

- Add/execute integration tests for retry cap enforcement and transient/terminal routing.
- Add/execute integration tests for DLQ insertion and replay path behavior.
- Validate structured logs/metrics for retry, DLQ, replay, and no-op outcomes.
- Update runbook procedures for DLQ triage and replay with actor/reason requirements.
- Out of scope: introducing new pipeline stages or changing quality gate rubric behavior.

## Inputs / Dependencies

- TASK-ST-029-01 retry classification matrix.
- TASK-ST-029-02 DLQ persistence model.
- TASK-ST-029-04 idempotent replay guard implementation.
- Existing runbooks under docs/runbooks.

## Implementation Notes

- Ensure integration evidence includes both successful recovery and safe no-op replay cases.
- Keep observability fields aligned with AGENDA_PLAN logging/metrics dimensions.
- Treat runbook clarity as release-blocking for operational handoff.

## Acceptance Criteria

1. Integration tests validate retry caps and transient/terminal routing behavior.
2. Integration tests validate DLQ persistence and replay workflow behavior.
3. Integration tests validate replay idempotency and no-duplicate publication safety.
4. Runbook and observability updates provide complete operator recovery guidance.

## Validation

- `pytest -q`
- Execute integration suites covering retry, DLQ, replay, and replay no-op safety.
- Validate runbook drill steps against staged terminal-failure scenarios.

## Deliverables

- Integration test coverage and result summary.
- Observability field/metric verification notes.
- Updated recovery runbook evidence bundle for operators.
