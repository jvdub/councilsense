# ST-022 Rollout Flag Matrix and Rollback Sequence

## Scope

- Story: `ST-022`
- Phase: Phase 0 contract/schema freeze controls for additive v1 rollout
- References:
  - `AGENDA_PLAN.md` §5 (Phase 0), §10 (decision log rollback order)
  - `docs/runbooks/st-022-v1-meeting-detail-contract.md`
  - `docs/runbooks/st-022-additive-schema-migration-sequence-plan.md`

## Rollout Principles

- Default-safe posture: ST-022 additive behavior remains off unless
  explicitly enabled.
- Additive-first rollout: enable schema writes before additive API
  projection, then UI, then notifications.
- Report-only before enforced: gate-like controls begin in
  `report_only`; `enforced` is allowed only after promotion checks pass.
- Rollback is flag-based and reversible without schema rollback.

## Rollout Flag Matrix

- `st022_schema_additive_writes_enabled`
  - Type: `bool`
  - Default: `false / false / false` (local/staging/prod)
  - Depends on: additive schema deployed
  - Enablement order: `1`
  - Environment progression:
    - local: on for fixture/backfill checks
    - staging: on for pilot city
    - prod: on for pilot cohort

- `st022_api_additive_v1_fields_enabled`
  - Type: `bool`
  - Default: `false / false / false`
  - Depends on: `st022_schema_additive_writes_enabled`
  - Enablement order: `2`
  - Environment progression:
    - local: on after contract fixture pass
    - staging: on after parity checks
    - prod: on after staged canary
  - Environment contract:
    - `ST022_API_ADDITIVE_V1_FIELDS_ENABLED=true|false`
    - `ST022_API_ADDITIVE_V1_BLOCKS=planned,outcomes,planned_outcome_mismatches`
  - Precedence / validation:
    - Default-safe baseline is `ST022_API_ADDITIVE_V1_FIELDS_ENABLED=false` with an empty `ST022_API_ADDITIVE_V1_BLOCKS` value.
    - `ST022_API_ADDITIVE_V1_BLOCKS` is required when the API additive flag is enabled.
    - `ST022_API_ADDITIVE_V1_BLOCKS` must stay empty when the API additive flag is disabled.
    - `planned_outcome_mismatches` is valid only when both `planned` and `outcomes` are also enabled.
    - Invalid combinations fail fast during startup with explicit diagnostics naming the offending env var.

- `st022_ui_planned_outcomes_enabled`
  - Type: `bool`
  - Default: `false / false / false`
  - Depends on: `st022_api_additive_v1_fields_enabled`
  - Enablement order: `3`
  - Environment progression:
    - local: developer validation
    - staging: internal users
    - prod: pilot cohort

- `st022_ui_mismatch_signals_enabled`
  - Type: `bool`
  - Default: `false / false / false`
  - Depends on:
    - `st022_ui_planned_outcomes_enabled`
    - `st022_api_additive_v1_fields_enabled`
  - Enablement order: `4`
  - Environment progression:
    - local: fixture-only
    - staging: internal users
    - prod: pilot cohort

- `st022_notifications_mismatch_enabled`
  - Type: `bool`
  - Default: `false / false / false`
  - Depends on: `st022_ui_mismatch_signals_enabled`
  - Enablement order: `5`
  - Environment progression:
    - local: synthetic notification tests
    - staging: pilot city
    - prod: pilot cohort

- `st022_gate_mode`
  - Type: enum (`report_only`|`enforced`)
  - Default: `report_only / report_only / report_only`
  - Depends on: diagnostics path available
  - Enablement order: cross-cutting after diagnostics readiness
  - Environment progression:
    - local: `report_only` only
    - staging: `enforced` only after 2 consecutive green report-only runs
    - prod: same promotion rule as staging

## Forward Rollout Sequence (Safe Order)

1. Confirm additive schema migration sequence is applied and stable
   (`TASK-ST-022-02` output).
2. Enable `st022_schema_additive_writes_enabled`.
3. Run ingest/extract/summarize/publish smoke for pilot city and verify
   dedupe/idempotency outcomes.
4. Enable `st022_api_additive_v1_fields_enabled`.
5. Verify API contract fixtures and baseline compatibility behavior.
6. Enable `st022_ui_planned_outcomes_enabled`.
7. Enable `st022_ui_mismatch_signals_enabled`.
8. Enable `st022_notifications_mismatch_enabled`.
9. Keep `st022_gate_mode=report_only` until two consecutive green
   report-only runs are recorded; then promote environment/cohort to
   `enforced`.

## Report-Only vs Enforced Operation

- `report_only`:
  - Emit diagnostics and reason codes.
  - Do not block publication creation.
  - Do not downgrade outputs solely due to gate failures.
- `enforced`:
  - Allowed only after two consecutive green report-only runs in the
    same environment/cohort.
  - Applies policy-driven block/downgrade behavior for gate failures.
  - Requires an audit trail with environment, cohort, trigger reason,
    and actor.

## Rollback Triggers and Conditions

Trigger rollback when any of the following occurs after a promotion:

- Contract regression: additive v1 fixture mismatch or missing required
  fields.
- Data integrity regression: duplicate publication/stage outcomes
  violating idempotency expectations.
- Operational regression: sustained publish failure spike, queue backlog
  growth, or error budget breach.
- Evidence/authority regression: incorrect authority alignment or
  materially degraded evidence precision coverage.

## Rollback Sequence (Required Reverse Order)

1. Set `st022_gate_mode=report_only` for affected environment/cohort.
2. Disable `st022_notifications_mismatch_enabled`.
3. Disable `st022_ui_mismatch_signals_enabled`.
4. Disable `st022_ui_planned_outcomes_enabled`.
5. Disable `st022_api_additive_v1_fields_enabled`.
6. Disable `st022_schema_additive_writes_enabled` only if
   schema-write-path instability is confirmed.

Do not perform destructive schema rollback in this sequence.

## Post-Step Safety Checks

After each rollback step, confirm before proceeding:

- New publish runs complete with baseline behavior.
- Meeting detail responses remain valid for legacy consumers.
- Error rate and queue/backlog metrics trend toward baseline.
- Diagnostics include rollback reason and current flag-state snapshot.

## Ownership and Change Authority

- Primary owner: platform/backend on-call for stage and API controls.
- Secondary owner: frontend on-call for UI flags.
- Escalation owner: release owner for promotion/rollback decisions.

All staging/prod transitions require recorded operator identity,
timestamp, and reason.
