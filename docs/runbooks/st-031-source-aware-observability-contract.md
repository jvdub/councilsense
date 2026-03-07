# ST-031 Source-Aware Observability Contract

## Purpose

This contract extends the ST-011 baseline with source-aware metrics for multi-document pipeline triage.

The scope for this task is limited to stage outcomes, coverage ratio, citation precision ratio, and pipeline DLQ backlog health.

## Stable Metrics

| Metric name | Type | Unit | Required labels | Description |
| --- | --- | --- | --- | --- |
| `councilsense_source_stage_outcomes_total` | counter | events | `stage`, `outcome`, `city_id`, `source_type`, `status` | Source-aware ingest, extract, compose, summarize, and publish outcome counts. |
| `councilsense_source_coverage_ratio` | gauge | ratio | `stage`, `outcome`, `city_id`, `source_type` | Bundle composition coverage ratio for expected source types. |
| `councilsense_source_citation_precision_ratio` | gauge | ratio | `stage`, `outcome`, `city_id`, `source_type` | Citation precision ratio for summarization evidence pointers. |
| `councilsense_pipeline_dlq_backlog_count` | gauge | entries | `stage`, `outcome`, `city_id`, `source_id`, `source_type` | Open pipeline DLQ backlog grouped by city, stage, and source registration. |
| `councilsense_pipeline_dlq_oldest_age_seconds` | gauge | seconds | `stage`, `outcome`, `city_id`, `source_id`, `source_type` | Oldest open pipeline DLQ age grouped by city, stage, and source registration. |

## Label Semantics

- `stage`: bounded pipeline stage name. For this dashboard, the primary triage stages are `ingest`, `extract`, `compose`, and pipeline DLQ source stages.
- `outcome`: bounded result or measurement state. Supported values in this task are `success`, `retry`, `failure`, `measured`, `missing_inputs`, `backlog`, and `oldest_age`.
- `city_id`: enabled city registry identifier.
- `source_type`: bounded source type enum `minutes`, `agenda`, `packet`, `bundle`, or `unknown`.
- `source_id`: enabled source registration identifier for pipeline DLQ snapshots only.
- `status`: bounded lifecycle value such as `processed`, `limited_confidence`, or `failed` for source stage outcomes.

## Cardinality Controls

- Labels MUST NOT include `meeting_id`, `run_id`, `artifact_id`, `bundle_id`, `dedupe_key`, `user_id`, or free-form error text.
- `city_id` and `source_id` are permitted only because they are bounded by enabled registry configuration and are required for operator triage.
- `source_id` is restricted to pipeline DLQ backlog gauges. It MUST NOT be added to stage outcome or quality-ratio metrics.
- Unknown or missing source values MUST normalize to `unknown` or `source-unknown` rather than creating new label values.
- Dashboard panels should aggregate by `city_id`, `stage`, and `source_type` first, then drill into `source_id` only for DLQ panels.

## Dashboard Order

The on-call triage order for this task is:

1. Source stage outcomes.
2. Source coverage ratio.
3. Citation precision ratio.
4. Pipeline DLQ backlog count.
5. Pipeline DLQ oldest age.

## Notes

- Alert routing and owner mappings are intentionally out of scope for TASK-ST-031-02.
- Authority-alignment metrics are deferred to later follow-up work.