# Phase 1.5: Notification DLQ + Replay Hardening

**Story ID:** ST-014  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** FR-5 (dead-letter handling in hardening), NFR-4 (DLQ visibility), Phase 1.5 (§9)

## User Story
As an operator, I want dead-letter handling and replay tooling so failed notifications can be recovered safely at operational cadence.

## Scope
- Add DLQ flow for exhausted notification attempts.
- Add replay tooling for dead-lettered notifications.
- Tune retry/backoff policies with measured outcomes.

## Acceptance Criteria
1. Exhausted notification attempts transition to DLQ state.
2. DLQ volume and replay outcomes are visible in operations dashboards.
3. Replay action can requeue eligible dead-lettered messages with audit trail.
4. Retry policy tuning is configuration-driven and documented.
5. Hardening implementation does not break MVP idempotency guarantees.

## Implementation Tasks
- [ ] Implement dead-letter transition and persistence schema for notifications.
- [ ] Implement operator replay endpoint/tooling with authorization.
- [ ] Add dashboard panels for DLQ and replay outcomes.
- [ ] Add policy configuration for retry limits/backoff tuning.
- [ ] Add resilience tests for replay idempotency and duplicate prevention.

## Dependencies
- ST-009
- ST-011

## Definition of Done
- Notification hard failures are recoverable through controlled replay.
- Operational visibility includes DLQ backlog and replay success rate.
- Idempotency and auditability remain intact during replay.
