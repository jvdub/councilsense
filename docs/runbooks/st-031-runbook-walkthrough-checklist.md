# ST-031 Runbook Walkthrough Checklist

Task: TASK-ST-031-04

Purpose: document-only walkthrough coverage for ST-031 runbook completeness. Final staging alert simulations remain deferred to TASK-ST-031-05.

## Representative Incident Coverage

| Alert class | Primary runbook entry | Supporting docs checked | Result |
| --- | --- | --- | --- |
| `parser_drift_spike` | `docs/runbooks/st-031-source-aware-incident-response.md` | `docs/runbooks/st-016-parser-drift-monitoring-runbook.md`, `docs/runbooks/st-010-health-and-confidence-policy.md` | PASS |
| `missing_minutes_surge` | `docs/runbooks/st-031-source-aware-incident-response.md` | `docs/runbooks/st-010-health-and-confidence-policy.md`, `docs/runbooks/st-031-source-aware-observability-contract.md` | PASS |
| `summarize_failure_spike` | `docs/runbooks/st-031-source-aware-incident-response.md` | `docs/runbooks/st-029-pipeline-dlq-contract.md`, `docs/runbooks/st-010-health-and-confidence-policy.md`, `docs/runbooks/st-021-quality-gates-rollout-and-rollback.md` | PASS |
| `stale_pipeline_dlq_backlog` | `docs/runbooks/st-031-source-aware-incident-response.md` | `docs/runbooks/st-029-pipeline-dlq-contract.md`, `docs/runbooks/st-021-quality-gates-rollout-and-rollback.md` | PASS |

## Completeness Checks

- [x] Each ST-031 alert class maps to one primary runbook entry point.
- [x] Primary owner, secondary owner, escalation target, and SLA are documented.
- [x] Replay procedure captures actor, reason, idempotency key, incident reference, and terminal outcome expectations.
- [x] Confidence-policy procedure captures limited-confidence decision metadata.
- [x] Rollback procedure maps alert escalation to `report_only` reversion and reverse-order flag disablement.

## Sign-Off Notes

- Desk walkthrough completed against the TASK-ST-031-03 alert matrix and current ST-029/ST-030/ST-010 support docs.
- No staging alert injection or end-to-end simulation was executed in this task.
- Runbook language is scoped to source-aware, source-scoped remediation and avoids destructive rollback guidance.
- TASK-ST-031-05 completed the staging simulation follow-through in `docs/runbooks/st-031-staging-alert-simulation-evidence.md`.

## Open Action List

- Closed by TASK-ST-031-05: staging alert simulation evidence now exists for each required alert class.
- Closed by TASK-ST-031-05: live walkthrough timestamps and follow-up operational tuning are recorded in the ST-031 staging evidence bundle.