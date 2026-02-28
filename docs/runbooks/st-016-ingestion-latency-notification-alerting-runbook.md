# ST-016 Ingestion, Latency, and Notification Alerting Runbook

## Scope

This runbook defines active alert rules for:

- ingestion failure rate
- pipeline publish latency (`p95`)
- notification delivery error rate

Rule source of truth: `config/ops/st-016-ingestion-latency-notification-alert-rules.json`.
Baseline thresholds and ownership source: `config/ops/st-016-alert-threshold-baseline.json`.

## Active Rule IDs

- `ingestion-failure-rate-warning`
- `ingestion-failure-rate-critical`
- `pipeline-latency-p95-warning`
- `pipeline-latency-p95-critical`
- `notification-delivery-error-rate-warning`
- `notification-delivery-error-rate-critical`

## Triage Metadata Contract

Required payload fields for every alert:

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

Escalation gating requirement: `city_id`, `source_id`, and `run_id` must exist before warning incidents are promoted.

## Ownership and Escalation Routing

- Ingestion failures: primary `ops-ingestion-oncall`, secondary `backend-oncall`, escalate `platform-owner`, SLA `PT30M`.
- Pipeline latency: primary `ops-pipeline-oncall`, secondary `backend-oncall`, escalate `platform-owner`, SLA `PT45M`.
- Notification errors: primary `ops-notifications-oncall`, secondary `backend-oncall`, escalate `platform-owner`, SLA `PT30M`.

## Environment Configuration

- `COUNCILSENSE_ALERT_RULES_ENABLED`: enables this ruleset.
- `COUNCILSENSE_ENVIRONMENT`: routes alerts by environment label.
- `COUNCILSENSE_ALERTS_NOTIFICATION_CHANNEL`: destination channel/receiver.
- `COUNCILSENSE_ALERTS_OWNER_MAPPING`: owner mapping source override.

## Alert Noise and Tuning

- Warning and critical severities follow ST-016 baseline thresholds.
- Alert fire counts are tracked by `councilsense_alert_rule_fires_total`.
- Acknowledgment metadata must capture `acknowledged_by`, `acknowledged_at_utc`, and `acknowledgment_note`.
