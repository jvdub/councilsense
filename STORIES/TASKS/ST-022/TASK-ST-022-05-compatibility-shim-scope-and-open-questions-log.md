# Compatibility Shim Scope and Open Questions Log

**Task ID:** TASK-ST-022-05  
**Story:** ST-022  
**Bucket:** docs  
**Requirement Links:** ST-022 Scope (compatibility shim optional), ST-022 Acceptance Criteria #4-#5, AGENDA_PLAN §10

## Status

- Completed: 2026-03-04
- Completion evidence:
  - `AGENDA_PLAN.md` §10 decision/open-questions register updated with owners, due dates, and rollout-control links.
  - Compatibility shim policy captured as optional and explicitly non-blocking for pre-launch.

## Objective

Document optional compatibility mapping scope and create a tracked decision log for unresolved contract questions with owners and due dates.

## Compatibility Shim Scope (Explicit Policy)

- Compatibility shims are optional and non-blocking for pre-launch.
- Pre-launch release criteria do **not** require a shim if additive v1 fields are available and baseline fields remain intact.
- Any shim work is limited to low-effort temporary mapping for legacy readers and must not delay Phase 1 rollout readiness.
- Rollout controls remain flag-first and reversible per `st022_api_additive_v1_fields_enabled` and `st022_ui_planned_outcomes_enabled` policy in `docs/runbooks/st-022-rollout-flag-matrix-and-rollback.md`.

## Scope

- Define what legacy compatibility mappings are in-scope vs explicitly deferred.
- Mark compatibility work as non-blocking for pre-launch release criteria.
- Record open contract/schema questions, owners, due dates, and decision status.
- Out of scope: building compatibility shims or changing release gates beyond documented policy.

## Inputs / Dependencies

- TASK-ST-022-01 approved v1 contract and fixtures.
- TASK-ST-022-04 rollout/rollback matrix.
- Product/platform ownership for contract decisions.

## Implementation Notes

- Keep log format easy to audit in planning and release reviews.
- Include explicit blocker status field (`blocking` or `non-blocking`) per question.
- Require closure criteria for each open item.

## Acceptance Criteria

1. Compatibility mapping scope is documented as optional and explicitly non-blocking. (ST-022 AC #4)
2. Open questions list includes owner, due date, and current status for each item. (ST-022 AC #5)
3. Resolved items include recorded decision outcome and date. (ST-022 AC #5)

## Open Questions Log (Unresolved)

| ID          | Question                                                                                          | Owner                               | Due Date   | Status | Blocker Status | Rollout Control Link                                                                           | Closure Criteria                                                                |
| ----------- | ------------------------------------------------------------------------------------------------- | ----------------------------------- | ---------- | ------ | -------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| ST022-OQ-01 | Should packet table extraction be modeled at row-level in MVP or deferred to hardening?           | Backend Lead (Pipeline)             | 2026-03-11 | Open   | non-blocking   | `st022_gate_mode=report_only` until decision is ratified for enforced checks                   | Decision recorded with scope (`MVP` or `Phase 1.5`) and fixture impact assessed |
| ST022-OQ-02 | What exact threshold defines high-severity mismatch notifications?                                | Product Owner + Notifications Owner | 2026-03-12 | Open   | non-blocking   | `st022_notifications_mismatch_enabled` remains off in staging/prod until threshold is approved | Threshold and reason-code mapping documented and reviewed                       |
| ST022-OQ-03 | Should mismatch comparison be limited to decisions/actions initially or include full claim graph? | Product Owner + Backend Lead        | 2026-03-13 | Open   | non-blocking   | Keep `st022_ui_mismatch_signals_enabled` rollout at internal/pilot scope only                  | Comparison scope and severity semantics approved                                |
| ST022-OQ-04 | What pilot backfill window is required (last 12 vs 24 months)?                                    | Data Platform Owner                 | 2026-03-14 | Open   | non-blocking   | Delay broad cohort expansion tied to `st022_schema_additive_writes_enabled`                    | Backfill window selected with cost/runtime estimate                             |
| ST022-OQ-05 | Which source-specific latency/error budgets are acceptable before automatic rollback triggers?    | SRE / Release Owner                 | 2026-03-15 | Open   | non-blocking   | Rollback trigger policy governs `st022_gate_mode` promotion and reversal                       | Budget thresholds approved and added to rollback trigger checklist              |

## Decision Log (Resolved)

| ID           | Decision                                      | Outcome                                                                 | Decision Date | Related Rollout Control                                                    |
| ------------ | --------------------------------------------- | ----------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------- |
| ST022-DEC-01 | Compatibility mapping as release prerequisite | Rejected; compatibility mapping is optional and non-blocking pre-launch | 2026-03-04    | `st022_api_additive_v1_fields_enabled` governs additive projection rollout |
| ST022-DEC-02 | Rollout control strategy for additive v1      | Approved; flag-driven sequence with report-only before enforced         | 2026-03-04    | `st022_gate_mode`, rollback reverse-order sequence                         |

## Validation

- Verify every unresolved question has owner and due date.
- Confirm release criteria do not require compatibility shims.
- Review decision log in cross-team planning meeting.

## Deliverables

- Compatibility shim scope statement.
- Open questions and decision log register.
- Updated release-readiness checklist references.
