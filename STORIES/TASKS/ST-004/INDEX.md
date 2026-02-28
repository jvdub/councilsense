# ST-004 Task Index — Scheduled Ingestion + Processing Orchestration

- Story: [ST-004 — Scheduled Ingestion + Processing Orchestration](../../ST-004-scheduled-ingestion-and-processing-orchestration.md)
- Requirement Links: MVP §4.3(1-3), FR-3, FR-7(4), NFR-1, NFR-2, NFR-5

## Ordered Checklist

- [x] [TASK-ST-004-01](TASK-ST-004-01-scheduler-city-enqueue.md) — Implement scheduler enqueue by enabled city
- [x] [TASK-ST-004-02](TASK-ST-004-02-stage-queue-contracts.md) — Define pipeline stage queue contracts
- [x] [TASK-ST-004-03](TASK-ST-004-03-run-lifecycle-persistence.md) — Persist run lifecycle and stage outcomes
- [x] [TASK-ST-004-04](TASK-ST-004-04-retry-and-failure-isolation.md) — Add retry policy and failure isolation behavior
- [ ] [TASK-ST-004-05](TASK-ST-004-05-orchestration-integration-tests.md) — Add orchestration integration tests

## Dependency Chain

- TASK-ST-004-01 -> TASK-ST-004-02
- TASK-ST-004-02 -> TASK-ST-004-03
- TASK-ST-004-03 -> TASK-ST-004-04
- TASK-ST-004-03 -> TASK-ST-004-05
- TASK-ST-004-04 -> TASK-ST-004-05

## Validation Commands

- `pytest -q`
