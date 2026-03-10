# Rollout Flag Matrix and Rollback Sequence

**Task ID:** TASK-ST-022-04  
**Story:** ST-022  
**Bucket:** ops  
**Requirement Links:** ST-022 Scope (rollout control matrix), ST-022 Acceptance Criteria #3, AGENDA_PLAN §10 Decision log

## Objective

Define a rollout/rollback control matrix with explicit flag names, default states, promotion order, and reversal order for agenda-plan v1 capabilities.

## Scope

- Enumerate rollout flags and default values by environment.
- Define enablement order for API additive fields, frontend rendering, and notification interactions.
- Define rollback order and verification checks for each reversal step.
- Out of scope: implementing flag infrastructure changes or executing production rollout.

## Inputs / Dependencies

- TASK-ST-022-02 additive schema plan.
- TASK-ST-022-03 stage ownership and idempotency contracts.
- Existing feature flag governance and runbook patterns.

## Implementation Notes

- Preserve baseline behavior when all new flags are disabled.
- Define reversible steps that avoid destructive schema dependency.
- Include explicit owner and authority for each flag/state transition.

## Acceptance Criteria

1. Matrix includes each flag name, default state, and environments/cohorts where applicable. (ST-022 AC #3)
2. Promotion and rollback order are explicit and operationally executable. (ST-022 AC #3)
3. Verification checkpoints are documented for each step to confirm safe transition. (ST-022 AC #3)

## Validation

- Tabletop walkthrough of forward rollout and full rollback.
- Validate baseline behavior with all new flags disabled.
- Confirm sequence alignment with decision-log rollback policy.

## Deliverables

- Rollout flag matrix document.
- Stepwise rollback procedure with post-check signals.
- Ownership and escalation contacts per control point.
