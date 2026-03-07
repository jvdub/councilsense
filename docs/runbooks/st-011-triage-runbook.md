# ST-011 Triage Runbook (Pipeline + Notifications)

This runbook maps top MVP failure modes to one dashboard panel and one log query so operators can quickly answer what failed, where, and when.

## Triage Defaults

- Time window: last 6 hours (`PT6H`) first, then expand to 24 hours if needed.
- Environment: non-local target (`aws`) during operational smoke and rehearsals.
- Correlation keys to carry through all steps: `city_id`, `meeting_id`, `run_id`, `dedupe_key`.

## Source-Aware Entry Point

- For ST-031 alert classes `parser_drift_spike`, `missing_minutes_surge`, `summarize_failure_spike`, and `stale_pipeline_dlq_backlog`, use `docs/runbooks/st-031-source-aware-incident-response.md` as the primary runbook.
- Preserve `source_id` and `stage` alongside the default correlation keys for every ST-031 handoff.

## Failure Mode 1: Pipeline Stage Failure

- Dashboard panel: `pipeline-stage-outcomes` (confirm failing stage/outcome volume).
- Supporting panel: `pipeline-stage-duration-p95` (check latency regression around failures).
- Log query:

```text
fields @timestamp, event.stage as stage, event.outcome as outcome, event.city_id as city_id,
  event.meeting_id as meeting_id, event.run_id as run_id, event.error as error
| filter event.event_name = "pipeline_stage_error"
| sort @timestamp desc
| limit 100
```

- Immediate action:
  - Identify dominant failing stage (`ingest`, `extract`, `summarize`, or `publish`).
  - Capture one representative `run_id` + `meeting_id` pair for incident notes.

## Failure Mode 2: Notification Delivery Failure

- Dashboard panel: `notification-delivery-outcomes` (inspect `retry` and `failure` outcomes).
- Supporting panel: `notification-delivery-duration-p95` (detect elevated delivery latency).
- Log query:

```text
fields @timestamp, event.outcome as outcome, event.error_code as error_code,
  event.error_summary as error_summary, event.city_id as city_id, event.meeting_id as meeting_id,
  event.run_id as run_id, event.dedupe_key as dedupe_key
| filter event.event_name = "notification_delivery_attempt"
| filter event.outcome in ["retry", "failure", "invalid_subscription", "expired_subscription"]
| sort @timestamp desc
| limit 100
```

- Immediate action:
  - Separate transient (`retry`) from terminal (`failure`, `invalid_subscription`, `expired_subscription`) outcomes.
  - If terminal failures spike, pause further fanout for affected provider until root cause is identified.

## Failure Mode 3: Stale or Failing Source

- Dashboard panel: `source-freshness-and-failure-snapshot`.
- Log query:

```text
fields @timestamp, event.city_id as city_id, event.meeting_id as meeting_id,
  event.run_id as run_id, event.source_id as source_id, event.stage as stage,
  event.outcome as outcome, event.error as error
| filter event.event_name = "pipeline_stage_error"
| filter event.stage = "ingest"
| sort @timestamp desc
| limit 100
```

- Immediate action:
  - Confirm whether stale source rows are due to repeated ingest errors versus expected source silence.
  - Open or update source-level triage item with `city_id` + `source_id` ownership.

## Escalation and Handoff

- Escalate if any failure mode remains unresolved after 60 minutes of active triage.
- Include in handoff: panel screenshot/export, one log query output, affected IDs (`city_id`, `meeting_id`, `run_id`), and current mitigation.

## Evidence Retention

- Record drill and incident notes in `docs/runbooks/st-011-smoke-rehearsal-evidence.md`.
- Keep all evidence in version control to preserve deterministic launch-readiness history.
