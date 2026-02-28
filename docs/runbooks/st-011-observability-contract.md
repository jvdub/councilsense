# ST-011 Observability Contract Baseline (Pipeline + Notifications)

## Purpose

This baseline defines canonical structured log fields, outcome labels, and metric naming conventions for pipeline and notification flows.

Scope is intentionally minimal for MVP and is foundational for subsequent ST-011 instrumentation tasks.

## Required Structured Log Keys

Every observability event for pipeline or notifications MUST include these keys:

- `city_id`
- `meeting_id`
- `run_id`
- `dedupe_key`
- `stage`
- `outcome`

### Key Conventions

- `city_id`, `meeting_id`, `run_id`, `dedupe_key`: non-empty strings.
- `stage`: bounded enum from the stage set below.
- `outcome`: bounded enum from the outcome set below.
- Optional context keys are allowed, but required keys above are mandatory for correlated triage.

## Closed Label Sets

### Stage labels (`stage`)

- `ingest`
- `extract`
- `summarize`
- `publish`
- `notify_enqueue`
- `notify_deliver`

### Outcome labels (`outcome`)

- `success`
- `failure`
- `retry`
- `suppressed`
- `invalid_subscription`
- `expired_subscription`
- `duplicate`

## Baseline Metrics

Metric names use prefix `councilsense_`, snake_case, and bounded labels only.

| Metric name | Type | Unit | Required labels | Description |
| --- | --- | --- | --- | --- |
| `councilsense_pipeline_stage_events_total` | counter | events | `stage`, `outcome` | Pipeline stage completion/failure counts. |
| `councilsense_pipeline_stage_duration_seconds` | histogram | seconds | `stage`, `outcome` | Pipeline stage elapsed duration. |
| `councilsense_notifications_enqueue_events_total` | counter | events | `stage`, `outcome` | Notification enqueue counts including dedupe outcomes. |
| `councilsense_notifications_delivery_events_total` | counter | events | `stage`, `outcome` | Notification delivery attempt outcomes. |
| `councilsense_notifications_delivery_duration_seconds` | histogram | seconds | `stage`, `outcome` | Notification delivery elapsed duration. |

### Cardinality Rules

- Metric labels MUST be bounded enums.
- Metric labels MUST NOT include high-cardinality identifiers (`city_id`, `meeting_id`, `run_id`, `dedupe_key`, `user_id`, `subscription_id`).
- High-cardinality identifiers belong in structured logs only.

## Structured Log Examples

Canonical examples are stored in:

- `backend/tests/fixtures/st011_observability_contract.json`

The fixture includes explicit success and failure examples for both pipeline and notification flows.

## Approval

- Backend owner: approved for ST-011 baseline scope.
- Ops owner: approved for ST-011 baseline scope.
- Approval date: 2026-02-28.
