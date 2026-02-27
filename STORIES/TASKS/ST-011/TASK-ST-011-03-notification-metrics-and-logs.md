# Notification Metrics and Logs

**Task ID:** TASK-ST-011-03  
**Story:** ST-011  
**Bucket:** backend  
**Requirement Links:** NFR-1, NFR-2, NFR-4

## Objective
Add notification enqueue/send telemetry for throughput, failures, retries, and latency.

## Scope
- In scope:
  - Counters for enqueue success/failure and send success/failure.
  - Retry attempt counters and terminal failure counters.
  - Delivery latency metric from publish to send outcome.
  - Structured logs for send lifecycle outcomes.
- Out of scope:
  - Dashboard visualizations.

## Inputs / Dependencies
- TASK-ST-011-01
- ST-009 delivery statuses and dedupe key

## Implementation Notes
- Reuse dedupe_key and run_id for traceability.
- Keep provider-specific error details normalized.
- Ensure metric dimensions stay bounded.

## Acceptance Criteria
1. Enqueue and send outcome counters are emitted.
2. Retry and terminal failure telemetry is emitted.
3. Delivery latency metric is emitted for successful and failed sends where applicable.

## Validation
- Run notification integration tests and assert metric emissions.
- Run log contract test for notification events.

## Deliverables
- Notification telemetry instrumentation.
- Metric and log assertion tests.
- Telemetry examples for dashboard wiring.
