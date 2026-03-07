# ST-028 Meeting Detail Render Mode Resolution

- Story: ST-028
- Task: TASK-ST-028-01
- Scope: frontend-only render-mode resolution for baseline vs additive meeting detail rendering

## Frontend flag contract

- `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED`
  - `false` by default
  - hard-disables additive meeting detail rendering
- `NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED`
  - `false` by default
  - only applies when `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED=true`
  - missing or invalid mismatch payload does not force baseline mode

## Deterministic precedence

1. If `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED` is not `true`, render `baseline`.
2. If `planned` is missing or invalid, render `baseline`.
3. If `outcomes` is missing or invalid, render `baseline`.
4. Otherwise render `additive`.
5. Inside `additive` mode, enable mismatch signals only when `NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED=true` and `planned_outcome_mismatches` is present and valid.
6. Missing or invalid `planned_outcome_mismatches` disables mismatch signals but preserves additive planned/outcomes mode.

## Payload contract checks

- `planned` required for additive mode:
  - `generated_at`
  - `source_coverage.minutes|agenda|packet`
  - `items[]` with `planned_id`, `title`, `category`, `status`, `confidence`
- `outcomes` required for additive mode:
  - `generated_at`
  - `authority_source=minutes`
  - `items[]` with `outcome_id`, `title`, `result`, `confidence`
- `planned_outcome_mismatches` optional for additive mode but required for mismatch signal rendering:
  - `summary.total|high|medium|low`
  - `items[]` with `mismatch_id`, `planned_id`, `outcome_id`, `severity`, `mismatch_type`, `description`, `reason_codes`

## Scenario matrix

| Planned/outcomes flag | Mismatch flag | `planned` | `outcomes` | `planned_outcome_mismatches` | Resolved mode | Mismatch signals |
| --------------------- | ------------- | --------- | ---------- | ---------------------------- | ------------- | ---------------- |
| off                   | off/on        | any       | any        | any                          | `baseline`    | disabled         |
| on                    | off           | valid     | valid      | any                          | `additive`    | disabled         |
| on                    | on            | valid     | valid      | valid                        | `additive`    | enabled          |
| on                    | on            | valid     | valid      | missing/invalid              | `additive`    | disabled         |
| on                    | on/off        | missing   | any        | any                          | `baseline`    | disabled         |
| on                    | on/off        | invalid   | any        | any                          | `baseline`    | disabled         |
| on                    | on/off        | valid     | missing    | any                          | `baseline`    | disabled         |
| on                    | on/off        | valid     | invalid    | any                          | `baseline`    | disabled         |

## Integration notes

- The meeting detail route resolves render mode once and exposes the result as non-visible DOM data attributes for downstream component tasks.
- Current baseline sections remain the only visible rendering path in TASK-ST-028-01.
- TASK-ST-028-02 and TASK-ST-028-03 should consume the resolved contract instead of re-deriving payload validity in UI components.

## TASK-ST-028-04 fallback hardening

- Baseline rendering must remain equivalent when `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED` is off, even if additive payload fields are present, partial, or malformed.
- Planned and outcomes sections render only when the resolved mode is `additive` and their corresponding contract blocks are `present`.
- Mismatch indicators render only when mismatch signals are enabled and the mismatch contract block is `present`; malformed mismatch payloads disable the component without affecting planned/outcomes mode.
- Unknown additive fields are ignored by the frontend. Only required contract fields control visibility and fallback behavior.

## Rollout and rollback notes

- Rollout: enable `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED=true` only after verifying representative meeting detail payloads include valid `planned` and `outcomes` blocks.
- Rollout: enable `NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED=true` only after verifying `planned_outcome_mismatches` is present and valid for the same payload set.
- Rollback: set `NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED=false` to remove mismatch indicators while retaining additive planned/outcomes sections.
- Rollback: set `NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED=false` to restore baseline-only meeting detail rendering regardless of additive payload drift.