# TASK-ST-009-05 Validation Evidence

Date: 2026-02-28
Story: ST-009
Task: TASK-ST-009-05 — Idempotency, Retry, and Failure Validation

## Scope Coverage

- ✅ End-to-end publish-to-delivery path validates one logical delivery per dedupe key.
- ✅ Retry flow validates transient failure retries and terminal max-attempt cutoff.
- ✅ Invalid/expired endpoints are suppressed and excluded from subsequent worker sends.
- ✅ Attempt rows capture triage metadata (`error_code`, `provider_response_summary`, `attempt_number`, `outcome`, `next_retry_at`).

## Executed Commands

1. `pytest -q backend/tests/test_notification_publish_transaction_fanout.py backend/tests/test_notification_delivery_worker_retry_and_suppression.py`
2. `pytest -q backend/tests/test_notification_publish_transaction_fanout.py backend/tests/test_notification_delivery_worker_retry_and_suppression.py`

## Pass/Fail Outcomes

- Command 1: PASS (`7 passed`)
- Command 2 (repeat idempotency rerun validation): PASS (`7 passed`)

## Operations Evidence Query Snippets

```sql
SELECT dedupe_key, COUNT(*) AS rows_per_key
FROM notification_outbox
GROUP BY dedupe_key
HAVING COUNT(*) > 1;
```

```sql
SELECT outbox_id, attempt_number, outcome, error_code, provider_response_summary, next_retry_at, attempted_at
FROM notification_delivery_attempts
ORDER BY attempted_at DESC, outbox_id ASC, attempt_number ASC;
```

```sql
SELECT status, COUNT(*) AS count
FROM notification_outbox
GROUP BY status
ORDER BY status ASC;
```

```sql
SELECT id, subscription_id, status, attempt_count, error_code, provider_response_summary
FROM notification_outbox
WHERE status IN ('invalid_subscription', 'expired_subscription')
ORDER BY updated_at DESC;
```
