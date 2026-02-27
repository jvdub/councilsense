# ST-016 Task Index — Alert Thresholds and Parser Drift Monitoring

- Story: [ST-016 — Phase 1.5: Alert Thresholds + Parser Drift Monitoring](../../ST-016-phase-1-5-alert-thresholds-and-parser-drift-monitoring.md)
- Requirement Links: FR-7(2), NFR-4, Phase 1.5 §9

## Ordered Checklist

- [ ] [TASK-ST-016-01](TASK-ST-016-01-alert-threshold-and-ownership-discovery.md) — Alert Threshold Baseline and Ownership Discovery
- [ ] [TASK-ST-016-02](TASK-ST-016-02-ingestion-latency-notification-alert-rules.md) — Alert Rules for Ingestion Failures, Latency, and Notification Errors
- [ ] [TASK-ST-016-03](TASK-ST-016-03-parser-version-and-drift-event-model.md) — Parser Version Tracking and Drift Event Model
- [ ] [TASK-ST-016-04](TASK-ST-016-04-source-freshness-regression-alerting.md) — Source Freshness Regression Alerting
- [ ] [TASK-ST-016-05](TASK-ST-016-05-synthetic-alert-validation-dashboard-and-runbook-linkage.md) — Synthetic Alert Validation, Dashboard Visibility, and Runbook Linkage

## Dependency Chain

- TASK-ST-016-01 -> TASK-ST-016-02
- TASK-ST-016-01 -> TASK-ST-016-03
- TASK-ST-016-02 -> TASK-ST-016-04
- TASK-ST-016-03 -> TASK-ST-016-04
- TASK-ST-016-02 -> TASK-ST-016-05
- TASK-ST-016-03 -> TASK-ST-016-05
- TASK-ST-016-04 -> TASK-ST-016-05

## Notes

- TASK-ST-016-01 is a required discovery step because alert thresholds and ownership are operationally dependent.
- Hardening outputs are measurable: alert precision, time-to-detect, parser drift event rate, freshness breach count.

## Validation Commands

- `pytest -q`
