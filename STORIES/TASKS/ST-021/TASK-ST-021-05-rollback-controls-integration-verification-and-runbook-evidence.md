# Rollback Controls, Integration Verification, and Runbook Evidence

**Task ID:** TASK-ST-021-05  
**Story:** ST-021  
**Bucket:** ops  
**Requirement Links:** ST-021 Acceptance Criteria #5, GAP_PLAN §Rollback, NFR-5

## Objective
Define and validate rollback controls that safely disable enforcement and feature flags in the required reverse order, with integration evidence for release operators.

## Scope
- Define rollback sequence: specificity retention -> evidence projection -> topic hardening -> report-only gates.
- Define operator controls and verification checkpoints for each rollback step.
- Produce integrated rollout/rollback verification evidence and runbook linkage.
- Out of scope: introducing new gate classes or changing gate rubric definitions.

## Inputs / Dependencies
- TASK-ST-021-03 enforced gate policy hooks.
- TASK-ST-021-04 promotion eligibility checks and evidence artifacts.
- Existing operations runbook structure under docs/runbooks.

## Implementation Notes
- Rollback path must be executable under incident conditions with minimal manual interpretation.
- Require explicit verification signal after each rollback step before continuing.
- Include rollback-to-shadow and rollback-to-baseline examples.

## Acceptance Criteria
1. Rollback procedure documents and validates reverse-order flag disabling plus gate mode reversion.
2. Each rollback step has explicit preconditions, command/control action, and post-check.
3. Integration verification covers rollout to enforced mode and rollback back to report-only/baseline.
4. Release owners have a single evidence bundle for promotion and rollback readiness.

## Validation
- Tabletop exercise for rollback sequence using a staged enforcement scenario.
- Execute integration verification checklist end-to-end in local/staging environment.
- Confirm runbook references and operator ownership metadata are complete.

## Deliverables
- Rollback control specification and stepwise verification checklist.
- Integrated rollout/rollback readiness evidence report.
- Runbook update requirements with linked operational ownership.
