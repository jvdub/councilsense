# Reversible Rollback Controls and Operations Drill Evidence

**Task ID:** TASK-ST-030-05  
**Story:** ST-030  
**Bucket:** ops  
**Requirement Links:** ST-030 Acceptance Criteria #4, ST-030 Acceptance Criteria #5, AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §10 Decision log and open questions

## Objective

Define and validate rollback controls that return enforcement to report-only/disabled mode without schema rollback, and capture drill evidence.

## Scope

- Define operator rollback sequence for document-aware enforcement flags and mode controls.
- Define pre-check/post-check verification checkpoints per rollback step.
- Execute promotion+rollback drills and capture end-to-end evidence artifacts.
- Out of scope: introducing new gate dimensions or changing threshold contracts.

## Inputs / Dependencies

- TASK-ST-030-03 enforced publish decisioning hooks.
- TASK-ST-030-04 promotion artifacts and eligibility results.
- Existing operations runbook structure and ownership model.

## Implementation Notes

- Rollback must be executable during incidents with minimal operator ambiguity.
- Sequence must restore report-only mode and/or disable flags without destructive schema changes.
- Drill evidence should include actor, timestamp, control action, and verification result.

## Acceptance Criteria

1. Rollback sequence to report-only and flag disable is documented and executable without schema rollback.
2. Each rollback step has clear preconditions, action, and post-check criteria.
3. Operational drill validates promotion and rollback controls end-to-end.
4. Runbook evidence package includes ownership and escalation routing.

## Validation

- Tabletop and staged execution of rollback sequence after enforced-mode simulation.
- Verify publish path returns to non-enforced baseline behavior after rollback.
- Confirm runbook and drill artifacts are complete for release sign-off.

## Deliverables

- Rollback controls specification with stepwise checks.
- Promotion/rollback drill script and execution evidence.
- Runbook update checklist and ownership mapping.
