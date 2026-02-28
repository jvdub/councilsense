# ST-014 DLQ Replay Observability Runbook Snippet

## Dashboard Panels

Use the ST-011 baseline dashboard panels:

- `notification-dlq-inflow`
- `notification-dlq-backlog-count`
- `notification-dlq-oldest-age-seconds`
- `notification-dlq-replay-outcomes`
- `notification-dlq-replay-success-rate`
- `notification-dlq-replay-failure-rate`
- `notification-dlq-replay-duplicate-prevention-hits`
- `notification-dlq-replay-audit-evidence-links`

## Operational Definitions

- Replay success rate = `requeued / (requeued + ineligible + duplicate)`.
- Replay failure rate = `ineligible / (requeued + ineligible + duplicate)`.
- Duplicate replay rate = `duplicate / (requeued + ineligible + duplicate)`.
- Duplicate-prevention hit count = `sum(councilsense_notifications_dlq_replay_duplicate_prevention_hits_total)`.

## Warning Threshold (Active)

- Alert ID: `notification-dlq-backlog-growth-warning`.
- Trigger when `councilsense_notifications_dlq_backlog_count` for `stage=notify_dlq` and `outcome=backlog` is `>= 5` for `15m`.
- This threshold is configured in `docs/runbooks/st-014-dlq-replay-alert-rules.json`.

## Response Steps

1. Open replay outcomes and backlog panels to confirm whether backlog growth is ongoing.
2. Filter by `city_id`, `source_id`, and `channel` tags in replay/DLQ events where available.
3. If replay failure rate rises with stable duplicate rate, investigate eligibility policy and payload validity.
4. If duplicate-prevention hits spike, confirm operator idempotency-key usage and replay tooling behavior.
5. Save replay evidence links and incident notes to `docs/runbooks/st-014-dlq-replay-audit-evidence.md`.
