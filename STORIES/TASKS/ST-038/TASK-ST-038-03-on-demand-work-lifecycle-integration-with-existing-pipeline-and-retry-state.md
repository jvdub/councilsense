# On-Demand Work Lifecycle Integration with Existing Pipeline and Retry State

**Task ID:** TASK-ST-038-03  
**Story:** ST-038  
**Bucket:** backend  
**Requirement Links:** ST-038 Acceptance Criteria #1, #3, and #4, FR-3, FR-7, NFR-4

## Objective

Integrate on-demand processing requests with the existing pipeline lifecycle so queued and in-progress work is tracked, retried, and audited through one authoritative model.

## Scope

- Reuse existing run/stage lifecycle records to represent on-demand queued and in-progress work.
- Attach enough context to distinguish on-demand resident-triggered work from scheduled work.
- Align active-work dedupe with existing retry and audit patterns.
- Out of scope: terminal-state reopening rules, frontend polling behavior, and operator UI changes.

## Inputs / Dependencies

- TASK-ST-038-01 active-work identity.
- TASK-ST-037-03 processing-request endpoint behavior.
- ST-029 retry and replay lifecycle patterns.

## Implementation Notes

- Avoid creating a separate queue model when the existing pipeline lifecycle can represent the state.
- Preserve auditability of who initiated on-demand work and why it was queued.
- Keep status projection aligned with the ST-037 response contract.

## Acceptance Criteria

1. On-demand work uses the existing pipeline lifecycle as the source of truth for active and terminal state. (supports ST-038 AC #1)
2. Resident-triggered work is auditable and distinguishable from scheduled work. (supports ST-038 AC #4)
3. Active-work dedupe integrates with retry lifecycle state without duplicate side effects.

## Validation

- Integration tests for queued and in-progress state transitions.
- Audit/assertion checks for resident-triggered work context.
- Verify retry-classified states remain consistent with existing ST-029 behavior.

## Deliverables

- On-demand lifecycle integration with processing runs/stages.
- Context/audit linkage for resident-triggered work.
- Integration coverage for queued/in-progress lifecycle behavior.
