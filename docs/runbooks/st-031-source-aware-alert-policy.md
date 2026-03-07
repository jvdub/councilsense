# ST-031 Source-Aware Alert Policy

Task: TASK-ST-031-03

This document defines the source-aware alert policy for multi-document parser drift spikes, missing-minutes surges, summarize failure spikes, and stale pipeline DLQ backlog.

Primary incident runbook: `docs/runbooks/st-031-source-aware-incident-response.md`

Machine-readable source of truth: `config/ops/st-031-source-aware-alert-rules.json`

## Threshold Matrix

| Alert class | Signal source | Warning threshold | Critical threshold | Evaluation window | Sustained condition |
| --- | --- | --- | --- | --- | --- |
| `parser_drift_spike` | `parser_drift_events` count grouped by city/source/parser version | `>= 2` drift events per `PT1H` (`local`: `>= 1`) | `>= 4` drift events per `PT1H` (`local`: `>= 2`) | `PT1H` | `PT15M` |
| `missing_minutes_surge` | `councilsense_source_coverage_ratio` observations `<= 0.6667` on `compose` bundle coverage | `>= 2` low-coverage observations per `PT30M` (`local`: `>= 1`) | `>= 4` low-coverage observations per `PT30M` (`local`: `>= 2`) | `PT30M` | `PT20M` |
| `summarize_failure_spike` | `councilsense_pipeline_stage_events_total` summarize failure rate | `>= 0.10` failure rate with denominator `>= 8` | `>= 0.20` failure rate with denominator `>= 8` | `PT15M` | `PT15M` |
| `stale_pipeline_dlq_backlog` | `councilsense_pipeline_dlq_oldest_age_seconds` gated by `councilsense_pipeline_dlq_backlog_count` | oldest age `>= 3600s` and backlog `>= 2` (`local`: `1800s` and backlog `>= 1`) | oldest age `>= 10800s` and backlog `>= 3` (`local`: `3600s` and backlog `>= 2`) | `PT30M` | `PT30M` |

## Severity Routing And Ownership

| Alert class | Primary role | Secondary role | Escalate to | Escalation SLA |
| --- | --- | --- | --- | --- |
| `parser_drift_spike` | `ops-ingestion-oncall` | `backend-oncall` | `platform-owner` | `PT45M` |
| `missing_minutes_surge` | `ops-ingestion-oncall` | `source-operations-owner` | `platform-owner` | `PT45M` |
| `summarize_failure_spike` | `ops-pipeline-oncall` | `backend-oncall` | `platform-owner` | `PT30M` |
| `stale_pipeline_dlq_backlog` | `ops-pipeline-oncall` | `backend-oncall` | `platform-owner` | `PT30M` |

## Alert Class To Runbook Mapping

| Alert class | Primary runbook entry | Primary remediation action |
| --- | --- | --- |
| `parser_drift_spike` | `docs/runbooks/st-031-source-aware-incident-response.md` | Validate drift context, stop unplanned parser rollout, and route affected output to limited-confidence handling when source integrity is uncertain. |
| `missing_minutes_surge` | `docs/runbooks/st-031-source-aware-incident-response.md` | Restore authoritative minutes coverage or keep the bundle in limited-confidence status until the source gap is resolved. |
| `summarize_failure_spike` | `docs/runbooks/st-031-source-aware-incident-response.md` | Stabilize summarize execution, use confidence-policy versus rollback decisioning, and replay only after mitigation. |
| `stale_pipeline_dlq_backlog` | `docs/runbooks/st-031-source-aware-incident-response.md` | Drain the source-scoped DLQ backlog with audited replay batches after the root cause is fixed. |

## Payload Contract

All alert payloads must include:

- `alert_class`
- `alert_id`
- `severity`
- `environment`
- `city_id`
- `source_id`
- `source_type`
- `run_id`
- `meeting_id`
- `stage`
- `observed_value`
- `threshold_value`
- `evaluation_window`
- `triggered_at_utc`
- `dashboard_path`
- `dashboard_panel_id`

Class-specific triage fields:

- `parser_drift_spike`: `parser_drift_event_id`, `baseline_run_id`, `baseline_parser_name`, `baseline_parser_version`, `current_parser_name`, `current_parser_version`, `delta_context_json`, `source_url`
- `missing_minutes_surge`: `coverage_ratio`, `coverage_floor`, `expected_missing_source_type`, `available_source_types`, `missing_source_types`, `authority_reason_codes`, `quality_gate_reason_codes`, `source_gap_hint`
- `summarize_failure_spike`: `failure_rate`, `failed_runs`, `total_runs`, `provider_used`, `fallback_reason`, `error_code`, `error_type`
- `stale_pipeline_dlq_backlog`: `dlq_key`, `terminal_reason`, `retry_policy_version`, `backlog_count`, `oldest_age_seconds`, `dlq_status`, `error_code`, `error_type`

Escalation gating requirement: `city_id`, `source_id`, and `run_id` must exist before incidents page beyond the owning team.

## Noise Controls

- Parser drift alerts dedupe on `alert_id`, `environment`, `city_id`, `source_id`, `source_type`, and `current_parser_version` for `PT2H`; they suppress during `planned_parser_rollout_window`.
- Missing-minutes alerts dedupe on `alert_id`, `environment`, and `city_id` for `PT90M`; they suppress during `planned_source_maintenance_window`.
- Summarize failure alerts dedupe on `alert_id`, `environment`, `city_id`, and `stage` for `PT2H`; they require at least eight summarize runs before a ratio-based page can fire.
- Stale DLQ alerts dedupe on `alert_id`, `environment`, `city_id`, `source_id`, and `stage` for `PT2H`; they suppress while an `active_dlq_replay_batch` is already draining the same backlog.
- All rules inherit a default repeat interval of `PT6H` and require acknowledgment metadata: `acknowledged_by`, `acknowledged_at_utc`, and `acknowledgment_note`.

## Diagnostic Links

- Parser drift: `docs/runbooks/st-016-synthetic-alert-validation-dashboard.json` panel `st016-parser-drift-events-weekly`, with `docs/runbooks/st-031-source-aware-incident-response.md` as the primary runbook and `docs/runbooks/st-016-parser-drift-monitoring-runbook.md` for parser delta analysis.
- Missing minutes surge: `docs/runbooks/st-031-source-aware-dashboard.json` panel `st031-source-coverage-ratio`, with `docs/runbooks/st-031-source-aware-incident-response.md` as the primary runbook and `docs/runbooks/st-031-source-aware-observability-contract.md` for label semantics.
- Summarize failure spike: `docs/runbooks/st-011-baseline-dashboards.json` panel `pipeline-stage-outcomes`, with `docs/runbooks/st-031-source-aware-incident-response.md` as the primary runbook and `docs/runbooks/st-031-source-aware-dashboard.json` for correlated coverage and citation signals.
- Stale pipeline DLQ backlog: `docs/runbooks/st-031-source-aware-dashboard.json` panel `st031-pipeline-dlq-oldest-age-by-source`, with `docs/runbooks/st-031-source-aware-incident-response.md` as the primary runbook and `docs/runbooks/st-029-pipeline-dlq-contract.md` for DLQ replay fields.

## Validation Scope

This task validates:

- trigger behavior for all four incident classes using controlled fixtures
- payload completeness against required common fields plus class-specific context
- dedupe and suppression behavior for repeated failures and planned-noise windows
- single-runbook linkage and document completeness via `docs/runbooks/st-031-runbook-walkthrough-checklist.md`

Staging simulation evidence remains deferred to TASK-ST-031-05.