# ST-031 Staging Alert Simulation And Walkthrough Evidence

Date: 2026-03-07  
Story: ST-031  
Task: TASK-ST-031-05  
Environment: staging

## Scope

- Repeatable staged simulations for `parser_drift_spike`, `missing_minutes_surge`, `summarize_failure_spike`, and `stale_pipeline_dlq_backlog`.
- Validation of trigger, route, acknowledgment, escalation, and runbook walkthrough outcomes.
- Release-readiness evidence with a follow-up action register.

## Repeatable Evidence Bundle

- Machine-readable bundle: `docs/runbooks/st-031-staging-alert-simulation-evidence.sample.json`
- Controlled trigger fixture: `backend/tests/fixtures/st031_alert_policy_validation.json`
- Alert rules: `config/ops/st-031-source-aware-alert-rules.json`

## Simulation Matrix

| Scenario | Alert class | Trigger result | Route and acknowledgment | Walkthrough result | Outcome |
| --- | --- | --- | --- | --- | --- |
| `st031-parser-drift-staging-critical` | `parser_drift_spike` | warning + critical fired | Routed to `ops-ingestion-oncall` and `backend-oncall`; acknowledged by `ops-ingestion-oncall`; escalated to `platform-owner` | Completed against `docs/runbooks/st-031-source-aware-incident-response.md` and parser drift support docs | PASS |
| `st031-missing-minutes-staging-critical` | `missing_minutes_surge` | warning + critical fired | Routed to `ops-ingestion-oncall` and `source-operations-owner`; acknowledged by `ops-ingestion-oncall`; escalation not required | Completed against `docs/runbooks/st-031-source-aware-incident-response.md` and confidence-policy guidance | PASS |
| `st031-summarize-failure-staging-critical` | `summarize_failure_spike` | warning + critical fired | Routed to `ops-pipeline-oncall` and `backend-oncall`; acknowledged by `ops-pipeline-oncall`; escalated to `platform-owner` | Completed against replay, confidence, and rollback branches of the primary runbook | PASS |
| `st031-stale-dlq-staging-critical` | `stale_pipeline_dlq_backlog` | warning + critical fired | Routed to `ops-pipeline-oncall` and `backend-oncall`; acknowledged by `backend-oncall`; escalation not required | Completed against DLQ replay and closure steps in the primary runbook | PASS |

## Walkthrough Results

- Parser drift drill confirmed that unplanned parser rollout handling preserves limited-confidence publication until parser override reversion is verified.
- Missing-minutes drill confirmed that isolated authoritative-source gaps are held at limited confidence without unsafe replay.
- Summarize failure drill confirmed provider mitigation first, then source-scoped replay, without broad rollback.
- Stale DLQ drill confirmed replay pre-checks, replay audit verification, and closure after backlog age stabilized.

## Follow-Up Action Register

| Action ID | Owner | Priority | Target date | Summary |
| --- | --- | --- | --- | --- |
| `st031-follow-up-001` | `backend-oncall` | high | 2026-03-12 | Automate planned parser rollout-window annotation for staging source overrides. |
| `st031-follow-up-002` | `source-operations-owner` | medium | 2026-03-14 | Add a staging source-silence probe for authoritative minutes feeds. |
| `st031-follow-up-003` | `platform-owner` | high | 2026-03-10 | Document summarize fallback readiness gates in the release checklist. |
| `st031-follow-up-004` | `ops-pipeline-oncall` | medium | 2026-03-11 | Add oldest-age delta verification to replay closure checks. |

## Release Readiness

- Overall result: `pass_with_follow_up_actions`
- Blocking issues: `0`
- Readiness decision: `ready_with_follow_up_actions`
- Review owner: `release-owner`

Targeted pytest coverage validates that the evidence bundle stays aligned with the ST-031 alert routing contract, repeatable trigger fixtures, and runbook linkage.