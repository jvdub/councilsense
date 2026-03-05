# ST-021 Quality Gates Enforcement Rollout and Rollback Controls

## Scope

- Story: `ST-021`
- Gate Matrix: Gate A (contract safety), Gate B (quality parity), Gate C (operational reliability)
- Feature flags: topic hardening, specificity retention, evidence projection

## Flag Contract and Precedence

`COUNCILSENSE_QG_CONFIG_JSON` is the canonical rollout contract.

Resolution order (highest precedence last):

1. `defaults`
2. `environments[<runtime_env>]`
3. `cohorts[<cohort>]`
4. `environment_cohorts[<runtime_env>:<cohort>]`

Supported fields:

- `topic_hardening_enabled` (bool)
- `specificity_retention_enabled` (bool)
- `evidence_projection_enabled` (bool)
- `gate_mode` (`report_only` | `enforced`)
- `enforcement_action` (`downgrade` | `block`)
- `promotion_required` (bool)
- `diagnostics_artifact_path` (string path, optional)

Invalid combination rejected at runtime:

- `gate_mode=report_only` with `enforcement_action=block`

Default safety posture when config is absent:

- Feature hardening defaults remain enabled.
- Gate mode defaults to `report_only`.
- Publish path remains non-blocking for shadow gate failures.

## Shadow Report-Only Behavior

Every publish-stage run emits shadow diagnostics for Gate A/B/C:

- gate identifier
- pass/fail state
- explicit reason codes
- environment/cohort attribution

Shadow mode **never** blocks publish.

Optional append-only diagnostics artifact path:

- `COUNCILSENSE_QG_DIAGNOSTICS_ARTIFACT_PATH`

## Enforced Mode Behavior

Enforcement is active only when:

1. `gate_mode=enforced`, and
2. promotion prerequisites are met (unless `promotion_required=false`).

Promotion prerequisite:

- 2 consecutive green runs across Gate A/B/C (complete diagnostics required)

Failure policy when enforced:

- `downgrade`: force publish to `limited_confidence` with enforcement reason codes
- `block`: return publish stage as `limited_confidence` and do not create publication record

Non-enforced cohorts keep existing publish behavior.

## Rollback Procedure (Required Reverse Order)

1. Disable `specificity_retention_enabled`
2. Disable `evidence_projection_enabled`
3. Disable `topic_hardening_enabled`
4. Revert `gate_mode` to `report_only`

Post-check each step before continuing.

## Evidence Bundle

- Shadow diagnostics: `config/ops/st-021-shadow-gate-diagnostics-report.json`
- Promotion readiness: `config/ops/st-021-promotion-readiness-report.json`
- Rollout/rollback readiness: `docs/runbooks/st-021-rollout-rollback-readiness-report.json`
