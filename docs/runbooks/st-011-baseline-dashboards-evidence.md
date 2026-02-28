# ST-011 Baseline Dashboard Evidence

Generated from deterministic fixture data in `backend/tests/fixtures/st011_dashboard_seed_telemetry.json`.

## Snapshot Metadata

- Environment filter: `local`
- Default dashboard time window: `PT6H`
- Scope: ingestion pipeline, notification enqueue/delivery, and source freshness/failure snapshot.

## Panel Evidence

### `pipeline-stage-outcomes`

- ingest/success = 18
- extract/failure = 2
- summarize/retry = 1

### `pipeline-stage-duration-p95`

- ingest/success duration sample = 12.4s
- extract/failure duration sample = 35.2s

### `notification-enqueue-outcomes`

- notify_enqueue/success = 9
- notify_enqueue/duplicate = 3

### `notification-delivery-outcomes`

- notify_deliver/success = 7
- notify_deliver/retry = 1
- notify_deliver/failure = 1

### `notification-delivery-duration-p95`

- notify_deliver/retry duration sample = 300s
- notify_deliver/failure duration sample = 360s

### `source-freshness-and-failure-snapshot`

Flagged rows from fixture:

| city_id | source_id | health_status | failure_streak | last_success_age_hours | last_failure_reason |
| --- | --- | --- | ---: | ---: | --- |
| city-eagle-mountain-ut | source-eagle-mountain-ut-minutes-primary | failing | 3 | 56.0 | http_500 |
| city-riverton-ut | source-riverton-ut-agenda-primary | degraded | 1 | 30.0 | parser_timeout |
