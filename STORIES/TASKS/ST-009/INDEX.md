# ST-009 Task Index — Idempotent Notification Fan-Out + Delivery

- Story: [ST-009 — Idempotent Notification Fan-Out + Delivery](../../ST-009-idempotent-notification-fanout-and-delivery.md)
- Requirement Links: MVP §4.4(1-4), FR-5, NFR-1, NFR-2, NFR-4

## Ordered Checklist

- [ ] [TASK-ST-009-01](TASK-ST-009-01-notification-contract-and-dedupe-key.md) — Notification Contract and Dedupe Key
- [ ] [TASK-ST-009-02](TASK-ST-009-02-outbox-and-attempt-schema.md) — Outbox and Attempt Schema
- [ ] [TASK-ST-009-03](TASK-ST-009-03-publish-transaction-fanout.md) — Publish Transaction Fan-Out
- [ ] [TASK-ST-009-04](TASK-ST-009-04-delivery-worker-retry-and-suppression.md) — Delivery Worker Retry and Suppression
- [ ] [TASK-ST-009-05](TASK-ST-009-05-idempotency-retry-and-failure-validation.md) — Idempotency, Retry, and Failure Validation

## Dependency Chain

- TASK-ST-009-01 -> TASK-ST-009-02
- TASK-ST-009-02 -> TASK-ST-009-03
- TASK-ST-009-02 -> TASK-ST-009-04
- TASK-ST-009-03 -> TASK-ST-009-05
- TASK-ST-009-04 -> TASK-ST-009-05

## Notes

- Keep dedupe deterministic across enqueue and send paths.
- Favor at-least-once infrastructure with exactly-once logical delivery via dedupe key.
- Capture attempt-level evidence for operations and future observability tasks.

## Validation Commands

- `pytest -q`
