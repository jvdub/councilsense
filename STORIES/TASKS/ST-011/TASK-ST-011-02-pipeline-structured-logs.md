# Pipeline Structured Logs

**Task ID:** TASK-ST-011-02  
**Story:** ST-011  
**Bucket:** backend  
**Requirement Links:** NFR-4

## Objective
Instrument ingestion and processing pipeline stages with structured logs aligned to the observability contract.

## Scope
- In scope:
  - Stage start/finish/error logs for fetch, parse, summarize, publish.
  - Correlation identifiers in every pipeline log.
  - Manual-review-needed outcome logging.
- Out of scope:
  - Notification delivery metrics.

## Inputs / Dependencies
- TASK-ST-011-01
- ST-010 state outputs

## Implementation Notes
- Ensure errors include stable error_code plus short message.
- Avoid logging sensitive payloads.
- Keep message templates consistent for queryability.

## Acceptance Criteria
1. Every pipeline stage emits start and finish or error events.
2. Correlation identifiers are present in all stage logs.
3. Manual-review outcomes are visible in structured logs.

## Validation
- Run pipeline integration test and assert log events by stage.
- Run log schema test for required keys.

## Deliverables
- Pipeline logging instrumentation changes.
- Log schema tests.
- Sample log capture artifact.
