# ST-021 Task Index — Quality Gates Enforcement, Rollout, and Rollback Controls

- Story: [ST-021 — Phase 1.5: Quality Gates Enforcement, Rollout, and Rollback Controls](../../ST-021-phase-1-5-quality-gates-enforcement-rollout-and-rollback-controls.md)
- Requirement Links: GAP_PLAN §Phase 4, GAP_PLAN §Gate Matrix (A/B/C), GAP_PLAN §Rollback, NFR-4, NFR-5

## Ordered Checklist

- [x] [TASK-ST-021-01](TASK-ST-021-01-quality-gate-flag-contract-and-cohort-config.md) — Quality Gate Feature Flag Contract and Cohort Configuration
- [x] [TASK-ST-021-02](TASK-ST-021-02-shadow-gate-evaluation-and-diagnostics-artifacts.md) — Shadow Gate Evaluation and Diagnostics Artifacts
- [x] [TASK-ST-021-03](TASK-ST-021-03-enforced-gate-policy-hooks-and-publish-decisioning.md) — Enforced Gate Policy Hooks and Publish Decisioning
- [x] [TASK-ST-021-04](TASK-ST-021-04-promotion-criteria-and-consecutive-green-gate-checks.md) — Promotion Criteria and Consecutive Green Gate Checks
- [x] [TASK-ST-021-05](TASK-ST-021-05-rollback-controls-integration-verification-and-runbook-evidence.md) — Rollback Controls, Integration Verification, and Runbook Evidence

## Dependency Chain

- TASK-ST-021-01 -> TASK-ST-021-02
- TASK-ST-021-02 -> TASK-ST-021-03
- TASK-ST-021-01 -> TASK-ST-021-04
- TASK-ST-021-02 -> TASK-ST-021-04
- TASK-ST-021-03 -> TASK-ST-021-05
- TASK-ST-021-04 -> TASK-ST-021-05

## Notes

- Keep rollout sequence explicit: report-only shadow mode first, then selective enforcement after promotion criteria are met.
- Rollback order must follow GAP_PLAN rollback guidance: specificity retention -> evidence projection -> topic hardening, then revert gates to report-only mode.
- Task 05 is release evidence for safe enforcement and safe rollback of Gate A/B/C behavior.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
