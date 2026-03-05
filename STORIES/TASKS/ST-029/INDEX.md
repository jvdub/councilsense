# ST-029 Task Index — Pipeline Retry Classification, DLQ, and Replay Audit

- Story: [ST-029 — Pipeline Retry Classification, DLQ, and Replay Audit](../../ST-029-pipeline-retry-classification-dlq-and-replay-audit.md)
- Requirement Links: AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 4 — Hardening: quality gates, retries, DLQ/replay, alerts (Weeks 8–10), AGENDA_PLAN §7 Observability, operations, and runbook updates

## Ordered Checklist

- [ ] [TASK-ST-029-01](TASK-ST-029-01-retry-policy-matrix-and-bounded-attempts-by-stage-source.md) — Retry Policy Matrix and Bounded Attempts by Stage/Source
- [ ] [TASK-ST-029-02](TASK-ST-029-02-pipeline-dlq-persistence-and-triage-context-contract.md) — Pipeline DLQ Persistence and Triage Context Contract
- [ ] [TASK-ST-029-03](TASK-ST-029-03-replay-command-flow-with-actor-reason-and-audit-history.md) — Replay Command Flow with Actor/Reason and Audit History
- [ ] [TASK-ST-029-04](TASK-ST-029-04-idempotent-replay-guards-and-publication-side-effect-protection.md) — Idempotent Replay Guards and Publication Side-Effect Protection
- [ ] [TASK-ST-029-05](TASK-ST-029-05-integration-tests-observability-and-runbook-recovery-evidence.md) — Integration Tests, Observability, and Runbook Recovery Evidence

## Dependency Chain

- TASK-ST-029-01 -> TASK-ST-029-02
- TASK-ST-029-01 -> TASK-ST-029-04
- TASK-ST-029-02 -> TASK-ST-029-03
- TASK-ST-029-03 -> TASK-ST-029-04
- TASK-ST-029-01 -> TASK-ST-029-05
- TASK-ST-029-02 -> TASK-ST-029-05
- TASK-ST-029-04 -> TASK-ST-029-05

## Notes

- Keep retry classification source-aware and bounded to prevent infinite retry loops.
- Route terminal failures into pipeline DLQ with complete triage context and replay metadata requirements.
- Replay must be actor-audited and idempotent, with explicit no-duplicate guarantees for publication side effects.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api pytest -q`
