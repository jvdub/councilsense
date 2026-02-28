# ST-014 DLQ Replay Audit Evidence

- Story: `ST-014`
- Task: `TASK-ST-014-04`
- Purpose: capture replay observability and audit metric validation evidence.

## Evidence Checklist

- Dashboard screenshots/exports for DLQ inflow, backlog count, oldest age, and replay outcomes.
- Replay success/failure/duplicate rate snapshots for the same time window.
- Alert simulation output for `notification-dlq-backlog-growth-warning`.
- Example replay audit rows (`notification_dlq_replay_audit`) with operator, reason, and outcome.

## Latest Validation

- Date: `2026-02-28`
- Result: `PASS`
- Notes: seeded telemetry and focused tests confirm DLQ/replay observability outputs and alert threshold behavior.
