# ST-022 Task Index — Agenda Plan v1 Contract, Schema, and Rollout Freeze

- Story: [ST-022 — Agenda Plan: v1 Contract, Schema, and Rollout Freeze](../../ST-022-agenda-plan-v1-contract-schema-and-rollout-freeze.md)
- Requirement Links: AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 0 — Contract and schema freeze (Week 1), AGENDA_PLAN §10 Decision log and open questions

## Ordered Checklist

- [x] [TASK-ST-022-01](TASK-ST-022-01-v1-contract-spec-and-fixtures.md) — v1 Contract Specification and Approval Fixtures
- [x] [TASK-ST-022-02](TASK-ST-022-02-additive-schema-migration-plan.md) — Additive Schema and Migration Sequence Plan
- [x] [TASK-ST-022-03](TASK-ST-022-03-idempotency-keys-and-stage-ownership-contract.md) — Idempotency Key Naming and Stage Ownership Contract
- [x] [TASK-ST-022-04](TASK-ST-022-04-rollout-flag-matrix-and-rollback-sequence.md) — Rollout Flag Matrix and Rollback Sequence
- [x] [TASK-ST-022-05](TASK-ST-022-05-compatibility-shim-scope-and-open-questions-log.md) — Compatibility Shim Scope and Open Questions Log

## Dependency Chain

- TASK-ST-022-01 -> TASK-ST-022-02
- TASK-ST-022-01 -> TASK-ST-022-03
- TASK-ST-022-02 -> TASK-ST-022-04
- TASK-ST-022-03 -> TASK-ST-022-04
- TASK-ST-022-01 -> TASK-ST-022-05
- TASK-ST-022-04 -> TASK-ST-022-05

## Notes

- Keep v1 payloads clean and versioned; compatibility mapping is optional and explicitly non-blocking for pre-launch.
- Treat schema work as additive-only and prohibit destructive changes in this phase.
- Track unresolved contract questions with named owners and due dates before implementation phases begin.

## Validation Commands

- `pytest -q`
- `python scripts/local_runtime_smoke.sh`
