# Scheduled Ingestion + Processing Orchestration

**Story ID:** ST-004  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.3(1-3), FR-3, FR-7(4), NFR-1, NFR-2, NFR-5

## User Story
As a platform operator, I want scheduled city-driven ingestion and processing so meetings are consistently available without manual intervention.

## Scope
- Implement scheduled pipeline trigger for configured cities.
- Implement async stages for ingest, extract, summarize, publish handoff.
- Persist run status lifecycle (`pending`, `processed`, `failed`, `limited_confidence`).
- Ensure failures are isolated per city/meeting.

## Acceptance Criteria
1. Scheduler triggers processing for enabled cities on configured cadence.
2. Pipeline runs independent of subscriber counts.
3. Run status and timestamps (`started_at`, `finished_at`) are recorded for each processing run.
4. Failure in one city/source does not block other city pipelines.
5. Failed jobs are retryable and visible in run state.

## Implementation Tasks
- [ ] Implement scheduler job that enqueues per-city scan jobs.
- [ ] Implement queue contracts for ingest/extract/summarize/publish stages.
- [ ] Persist processing run lifecycle and stage outcome metadata.
- [ ] Add retry policy and classify transient vs permanent errors.
- [ ] Add integration tests for multi-city failure isolation and retry.

## Dependencies
- ST-003

## Definition of Done
- Automated city-driven processing runs end-to-end on schedule.
- Pipeline state is queryable for operations and debugging.
- Isolation and retry behavior is verified in automated tests.
