# Observability Contract

**Task ID:** TASK-ST-011-01  
**Story:** ST-011  
**Bucket:** docs  
**Requirement Links:** NFR-4, NFR-1, NFR-2

## Objective
Define canonical structured log fields, metric names, and outcome labels for ingestion and notification flows.

## Scope
- In scope:
  - Required log keys: city_id, meeting_id, run_id, dedupe_key, stage, outcome.
  - Baseline metrics for count, failure, and duration.
  - Naming and label conventions to avoid cardinality problems.
- Out of scope:
  - Instrumentation code changes.

## Inputs / Dependencies
- ST-004 pipeline lifecycle
- ST-009 notification lifecycle
- ST-010 health/manual review states

## Implementation Notes
- Use one source-of-truth schema document.
- Include explicit examples for success and failure events.
- Keep labels bounded and low cardinality.

## Acceptance Criteria
1. Contract document lists required keys and metric definitions.
2. Outcome label set is closed and documented.
3. Contract is approved by backend and ops owners.

## Validation
- Lint structured log schema examples.
- Validate metric name uniqueness in telemetry config tests.

## Deliverables
- Observability contract document.
- Telemetry naming checklist.
- Schema example fixtures.
