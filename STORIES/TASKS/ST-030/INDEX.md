# ST-030 Task Index — Document-Aware Quality Gates and Authority Alignment Enforcement

- Story: [ST-030 — Document-Aware Quality Gates and Authority Alignment Enforcement](../../ST-030-document-aware-quality-gates-and-authority-alignment-enforcement.md)
- Requirement Links: AGENDA_PLAN §5 Phase 4 — Hardening, AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §8 Risks and mitigations, AGENDA_PLAN §10 Decision log and open questions

## Ordered Checklist

- [x] [TASK-ST-030-01](TASK-ST-030-01-document-aware-gate-dimensions-and-threshold-contract.md) — Document-Aware Gate Dimensions and Threshold Contract
- [x] [TASK-ST-030-02](TASK-ST-030-02-report-only-gate-diagnostics-and-artifacts.md) — Report-Only Gate Diagnostics and Artifacts
- [x] [TASK-ST-030-03](TASK-ST-030-03-enforced-publish-decisioning-for-document-aware-gates.md) — Enforced Publish Decisioning for Document-Aware Gates
- [x] [TASK-ST-030-04](TASK-ST-030-04-promotion-controller-for-consecutive-green-report-only-runs.md) — Promotion Controller for Consecutive Green Report-Only Runs
- [x] [TASK-ST-030-05](TASK-ST-030-05-reversible-rollback-controls-and-operations-drill-evidence.md) — Reversible Rollback Controls and Operations Drill Evidence

## Dependency Chain

- TASK-ST-030-01 -> TASK-ST-030-02
- TASK-ST-030-02 -> TASK-ST-030-03
- TASK-ST-030-01 -> TASK-ST-030-04
- TASK-ST-030-02 -> TASK-ST-030-04
- TASK-ST-030-03 -> TASK-ST-030-05
- TASK-ST-030-04 -> TASK-ST-030-05

## Notes

- Task sequencing maps directly to story acceptance criteria: diagnostics in report-only mode first, then enforced decisioning, then promotion, then rollback drills.
- Authority-alignment and source-conflict handling must follow AGENDA_PLAN risk mitigation guidance and remain reversible without schema rollback.
- Promotion and rollback evidence from Tasks 04/05 is the release-readiness artifact for this story.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
