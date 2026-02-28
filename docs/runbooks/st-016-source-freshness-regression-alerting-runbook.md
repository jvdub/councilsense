# ST-016 Source Freshness Regression Alerting Runbook

## Scope

This runbook defines source freshness regression alerting and suppression handling for planned maintenance windows.

Rule source of truth: `config/ops/st-016-source-freshness-regression-alert-rules.json`.
Baseline thresholds and ownership source: `config/ops/st-016-alert-threshold-baseline.json`.

## Active Rule IDs

- `source-freshness-regression-warning`
- `source-freshness-regression-critical`

## Triage Metadata Contract

Required payload fields:

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
- `last_success_at`
- `last_success_age_hours`
- `source_type`
- `source_url`
- `parser_drift_event_id`

Escalation gating requirement: `city_id`, `source_id`, and `run_id`.

## Suppression Rules

- Only planned windows with `window_label = planned_maintenance_window` suppress paging.
- Suppressed freshness breaches are still recorded for trend analysis.
- Unscheduled regressions outside windows always remain actionable.

## Ownership and Escalation Routing

- Freshness warnings/criticals: primary `ops-ingestion-oncall`, secondary `source-operations-owner`, escalate `platform-owner`, SLA `PT60M`.
