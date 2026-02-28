# ST-016 Alert Threshold and Ownership Baseline

**Date:** 2026-02-28  
**Story:** ST-016  
**Task:** TASK-ST-016-01  
**Requirement Links:** FR-7(2), NFR-4

This baseline defines initial hardening thresholds, severity mapping, and on-call ownership routing for core alert classes. Thresholds are provisional and scheduled for post-launch tuning after one month of production telemetry.

Machine-readable source of truth: `config/ops/st-016-alert-threshold-baseline.json`

## Threshold Matrix

| Alert class | Signal | Warning threshold | Critical threshold | Evaluation window | False-positive tolerance | Provisional tuning review |
| --- | --- | --- | --- | --- | --- | --- |
| ingestion failures | ingest stage failure rate | `>= 5%` for `15m` | `>= 10%` for `15m` | `15m` | `<=2` warning pages / 7 days | 2026-03-31 |
| pipeline latency | publish stage `p95` duration | `>= 1800s` for `20m` | `>= 3600s` for `20m` | `30m` | `<=1` critical page / 14 days | 2026-03-31 |
| notification errors | notify deliver error rate | `>= 3%` for `15m` | `>= 7%` for `15m` | `15m` | `<=3` warning pages / 7 days | 2026-03-31 |
| source freshness | last successful ingest age | `>= 24h` for `30m` | `>= 48h` for `30m` | `1h` | `<=1` warning/source / 14 days | 2026-03-31 |

## Severity and Ownership Routing

| Alert class | Warning severity | Critical severity | Primary owner role | Secondary role | Escalate to | Escalation SLA |
| --- | --- | --- | --- | --- | --- | --- |
| ingestion failures | warning | critical | `ops-ingestion-oncall` | `backend-oncall` | `platform-owner` | `PT30M` |
| pipeline latency | warning | critical | `ops-pipeline-oncall` | `backend-oncall` | `platform-owner` | `PT45M` |
| notification errors | warning | critical | `ops-notifications-oncall` | `backend-oncall` | `platform-owner` | `PT30M` |
| source freshness | warning | critical | `ops-ingestion-oncall` | `source-operations-owner` | `platform-owner` | `PT60M` |

## Required Triage Metadata

Every alert emission and incident note must include:

- `alert_class`
- `alert_id`
- `city_id`
- `source_id`
- `run_id`
- `meeting_id`
- `stage`
- `outcome`
- `environment`
- `observed_value`
- `threshold_value`
- `evaluation_window`
- `triggered_at_utc`

Minimum handoff requirement: `city_id`, `source_id`, and `run_id` must be present before escalation from warning to incident state.

## Operational Unknowns (Tracked)

| Unknown ID | Open unknown | Owner | Due date | Status |
| --- | --- | --- | --- | --- |
| st016-unknown-001 | Overnight freshness gap variance by source cadence may over-page low-frequency sources. | `ops-ingestion-oncall` | 2026-03-21 | open |
| st016-unknown-002 | Provider-side push error mix baseline is incomplete for provider-specific threshold tuning. | `ops-notifications-oncall` | 2026-03-21 | open |
| st016-unknown-003 | Publish stage p95 sensitivity under agenda-heavy seasonal peaks is not fully characterized. | `ops-pipeline-oncall` | 2026-03-28 | open |

## Escalation Mapping Notes

- Warning alerts create an ops triage ticket assigned to the primary owner role.
- Critical alerts page primary and secondary roles and require escalation acknowledgement within the listed SLA.
- If metadata is incomplete (`city_id`/`source_id`/`run_id` missing), alert is routed to `backend-oncall` for telemetry contract gap remediation.
- This discovery artifact intentionally defines baseline routing only; concrete alert rule implementation is deferred to TASK-ST-016-02.

## Approval

- Ops owner: approved baseline thresholds and ownership routing for hardening start.
- Backend owner: approved triage metadata requirements and escalation handoff contract.
