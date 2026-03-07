# ST-030 Reversible Rollback Controls and Operations Drill Evidence

## Scope

- Story: `ST-030`
- Task: `TASK-ST-030-05`
- Objective: return document-aware enforcement to `report_only` or fully disabled mode without schema rollback, and capture promotion plus rollback drill evidence for release sign-off.

## Rollback Principles

- Use config and flag changes only. Do not perform schema rollback.
- Restore `gate_mode=report_only` first when publish enforcement must be removed immediately.
- Disable document-aware feature flags only after the publish path is confirmed back in non-enforced behavior.
- Record actor, timestamp, reason, and verification result for every promotion or rollback control action.

## Ownership And Escalation

- Primary owner: platform/backend on-call
- Secondary owner: release owner
- Escalation owner: incident commander
- Paging route: platform/backend on-call -> release owner -> incident commander
- Escalate when any rollback post-check fails, publish remains enforced after the `report_only` reversion step, or baseline behavior is not restored within 15 minutes.

## Promotion Pre-Checks

Complete these checks before a drill or staged promotion:

1. Capture the latest promotion artifact from `COUNCILSENSE_QG_PROMOTION_ARTIFACT_PATH` and verify `eligible=true` with two consecutive green report-only runs.
2. Capture the latest diagnostics artifact from `COUNCILSENSE_QG_DIAGNOSTICS_ARTIFACT_PATH` and verify the affected environment/cohort matches the promotion scope.
3. Record operator identity, timestamp, ticket or incident reference, and the intended scope (`environment`, `cohort`, `promotion_scope_key`).
4. Confirm the rollback operator has authority to modify `COUNCILSENSE_QG_CONFIG_JSON` for the target environment.

## Rollback Profile: Report-Only Reversion

Use this profile first during incidents when enforcement must stop immediately and diagnostics should continue.

### Step 1: `gate_mode -> report_only`

- Pre-check: confirm the target environment/cohort currently resolves `gate_mode=enforced` and capture the promotion artifact run IDs for the incident record.
- Action: update `COUNCILSENSE_QG_CONFIG_JSON` so the affected environment/cohort resolves `gate_mode=report_only`, then reload or redeploy the runtime that consumes the config.
- Post-check: run one verification publish and confirm `quality_gate_rollout.gate_mode=report_only` and `quality_gate_rollout.enforcement_outcome.decision=observe` in publish metadata.

Stop here if the incident objective is only to remove enforcement.

## Rollback Profile: Full Disable After Report-Only

Use this profile only after report-only reversion is complete or an equivalent manual override proves publish has already returned to non-enforced behavior.

### Step 1: `specificity_retention_enabled -> false`

- Pre-check: confirm `gate_mode=report_only` for the affected environment/cohort.
- Action: disable `specificity_retention_enabled` in `COUNCILSENSE_QG_CONFIG_JSON` and reload the target runtime.
- Post-check: verification output no longer applies anchor carry-through behavior and diagnostics still emit for the run.

### Step 2: `evidence_projection_enabled -> false`

- Pre-check: confirm `specificity_retention_enabled=false` in the resolved config.
- Action: disable `evidence_projection_enabled` and reload the target runtime.
- Post-check: verification output no longer applies additive evidence projection precision behavior.

### Step 3: `topic_hardening_enabled -> false`

- Pre-check: confirm `specificity_retention_enabled=false` and `evidence_projection_enabled=false` in the resolved config.
- Action: disable `topic_hardening_enabled` and reload the target runtime.
- Post-check: publish path is operating on the non-enforced baseline without any schema rollback.

## Drill Procedure

1. Complete promotion pre-checks and record the artifact run IDs.
2. Promote the target environment/cohort from `report_only` to `enforced`.
3. Run a staged publish verification and record the publish decision plus reason codes.
4. Execute the report-only rollback profile.
5. Run a verification publish and confirm observational behavior is restored.
6. If needed, execute the full-disable profile in the documented order and verify baseline behavior after each step.
7. Save the evidence package with actor, timestamp, control action, and verification result for each promotion and rollback step.

## Required Evidence Package

- Promotion artifact reference with evaluated run IDs and eligibility result.
- Diagnostics artifact reference tied to the same promotion scope.
- Ordered action log for promotion and rollback, including actor, timestamp, previous value, new value, and verification result.
- Ownership and escalation routing used for the drill.
- Final post-check confirming publish returned to non-enforced baseline behavior without schema rollback.

Sample evidence artifact: `docs/runbooks/st-030-promotion-rollback-drill-evidence.sample.json`