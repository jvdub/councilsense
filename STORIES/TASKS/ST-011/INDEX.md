# ST-011 Task Index — Observability Baseline for Pipeline + Notifications

- Story: [ST-011 — Observability Baseline for Pipeline + Notifications](../../ST-011-observability-baseline-for-pipeline-and-notifications.md)
- Requirement Links: NFR-4, NFR-1, NFR-2

## Ordered Checklist

- [ ] [TASK-ST-011-01](TASK-ST-011-01-observability-contract.md) — Observability Contract
- [ ] [TASK-ST-011-02](TASK-ST-011-02-pipeline-structured-logs.md) — Pipeline Structured Logs
- [ ] [TASK-ST-011-03](TASK-ST-011-03-notification-metrics-and-logs.md) — Notification Metrics and Logs
- [ ] [TASK-ST-011-04](TASK-ST-011-04-baseline-dashboards.md) — Baseline Dashboards
- [ ] [TASK-ST-011-05](TASK-ST-011-05-smoke-validation-and-triage-runbook.md) — Smoke Validation and Triage Runbook

## Dependency Chain

- TASK-ST-011-01 -> TASK-ST-011-02
- TASK-ST-011-01 -> TASK-ST-011-03
- TASK-ST-011-02 -> TASK-ST-011-04
- TASK-ST-011-03 -> TASK-ST-011-04
- TASK-ST-011-04 -> TASK-ST-011-05

## Notes

- Prioritize actionable telemetry over exhaustive coverage.
- Include identifiers needed to trace one meeting from ingest to notification outcome.
- Keep this baseline lightweight and compatible with later hardening stories.

## Validation Commands

- `pytest -q`
