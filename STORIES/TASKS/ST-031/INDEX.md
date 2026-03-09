# ST-031 Task Index — Multi-Document Observability, Alerts, and Runbook Completion

- Story: [ST-031 — Multi-Document Observability, Alerts, and Runbook Completion](../../ST-031-multi-document-observability-alerts-and-runbook-completion.md)
- Requirement Links: AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §6 Testing and validation plan, AGENDA_PLAN §8 Risks and mitigations

## Ordered Checklist

- [x] [TASK-ST-031-01](TASK-ST-031-01-structured-log-correlation-context-for-multi-document-pipeline.md) — Structured Log Correlation Context for Multi-Document Pipeline
- [x] [TASK-ST-031-02](TASK-ST-031-02-source-aware-metrics-and-dashboard-panels.md) — Source-Aware Metrics and Dashboard Panels
- [x] [TASK-ST-031-03](TASK-ST-031-03-alert-policies-for-drift-failure-spikes-and-dlq-health.md) — Alert Policies for Drift, Failure Spikes, and DLQ Health
- [x] [TASK-ST-031-04](TASK-ST-031-04-runbook-updates-for-triage-replay-confidence-and-rollback.md) — Runbook Updates for Triage, Replay, Confidence, and Rollback
- [x] [TASK-ST-031-05](TASK-ST-031-05-staging-alert-simulations-and-runbook-walkthrough-evidence.md) — Staging Alert Simulations and Runbook Walkthrough Evidence

## Dependency Chain

- TASK-ST-031-01 -> TASK-ST-031-02
- TASK-ST-031-01 -> TASK-ST-031-03
- TASK-ST-031-02 -> TASK-ST-031-03
- TASK-ST-031-02 -> TASK-ST-031-04
- TASK-ST-031-03 -> TASK-ST-031-04
- TASK-ST-031-04 -> TASK-ST-031-05

## Notes

- Story sequencing follows observability implementation order: logging context first, then metrics/dashboards, then alerts, then runbooks, then staged simulations.
- Alert definitions must align with AGENDA_PLAN risk areas: parser drift, missing-minutes surges, summarize failures, and DLQ backlog staleness.
- Task 05 provides release evidence that alert routes and runbook procedures are operationally complete.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
