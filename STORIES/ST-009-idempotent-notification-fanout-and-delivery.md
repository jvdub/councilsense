# Idempotent Notification Fan-Out + Delivery

**Story ID:** ST-009  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.4(1-4), FR-5, NFR-1, NFR-2, NFR-4

## User Story
As a subscribed user, I want exactly one timely push notification per newly published meeting so I’m informed without duplicates.

## Scope
- Fan-out notifications to subscribed users by city on successful publish.
- Enforce deterministic dedupe key for idempotent sends.
- Implement bounded retry/backoff and delivery attempt logging.
- Suppress invalid/expired subscriptions until refreshed.

## Acceptance Criteria
1. Successful meeting publish enqueues notification work for eligible subscribers in that city.
2. Duplicate enqueue/send attempts do not produce duplicate logical deliveries due to deterministic dedupe key enforcement.
3. Retry/backoff policy is configurable and bounded by max attempts.
4. Delivery attempts and failures are persisted for operations visibility.
5. Invalid/expired subscriptions are marked and excluded from further sends.

## Implementation Tasks
- [ ] Implement outbox fan-out write in publish transaction.
- [ ] Enforce unique dedupe key (`user_id + meeting_id + notification_type`).
- [ ] Implement worker send loop with retry/backoff and status transitions.
- [ ] Persist attempt-level audit rows and failure metadata.
- [ ] Add tests for idempotency, retries, and invalid-subscription suppression.

## Dependencies
- ST-002
- ST-005
- ST-008

## Definition of Done
- Notification path reliably produces one logical delivery per user/meeting/type.
- Retry and suppression behavior is measurable in DB/logs.
- Acceptance tests validate baseline reliability policy.
