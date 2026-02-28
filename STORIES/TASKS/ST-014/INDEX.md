# ST-014 Task Index — Notification DLQ and Replay Hardening

- Story: [ST-014 — Phase 1.5: Notification DLQ + Replay Hardening](../../ST-014-phase-1-5-notification-dlq-and-replay-hardening.md)
- Requirement Links: FR-5 (hardening DLQ), NFR-4, Phase 1.5 §9

## Ordered Checklist

- [x] [TASK-ST-014-01](TASK-ST-014-01-dlq-schema-and-terminal-failure-transition.md) — DLQ Schema and Terminal Failure Transition
- [x] [TASK-ST-014-02](TASK-ST-014-02-retry-policy-configuration-and-exhaustion-rules.md) — Retry Policy Configuration and Exhaustion Rules
- [x] [TASK-ST-014-03](TASK-ST-014-03-operator-replay-api-and-authorization.md) — Operator Replay API and Authorization
- [x] [TASK-ST-014-04](TASK-ST-014-04-dlq-replay-observability-and-audit-metrics.md) — DLQ and Replay Observability with Measurable Outputs
- [ ] [TASK-ST-014-05](TASK-ST-014-05-replay-idempotency-and-duplicate-prevention-tests.md) — Replay Idempotency and Duplicate Prevention Test Gate

## Dependency Chain

- TASK-ST-014-01 -> TASK-ST-014-02
- TASK-ST-014-01 -> TASK-ST-014-03
- TASK-ST-014-02 -> TASK-ST-014-03
- TASK-ST-014-03 -> TASK-ST-014-04
- TASK-ST-014-03 -> TASK-ST-014-05
- TASK-ST-014-04 -> TASK-ST-014-05

## Notes

- Hardening outputs are measurable: DLQ backlog, replay success rate, replay duplicate rate.
- Task 05 is the gate to prove idempotency guarantees remain intact.

## Validation Commands

- `pytest -q`
