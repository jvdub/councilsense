# Source Freshness Regression Alerting

**Task ID:** TASK-ST-016-04  
**Story:** ST-016  
**Bucket:** backend  
**Requirement Links:** NFR-4, ST-016 Acceptance Criteria #3 and #4

## Objective
Implement freshness regression detection and operational warning alerts based on last-success age thresholds.

## Scope
- Compute source freshness age against configured thresholds.
- Emit warning/critical freshness alerts with triage metadata.
- Store freshness breach events for trend reporting.
- Out of scope: general ingestion/latency alert rules.

## Inputs / Dependencies
- TASK-ST-016-01 threshold and ownership matrix.
- TASK-ST-016-03 source/run metadata and drift context.

## Implementation Notes
- Distinguish expected low-frequency sources from stale-source failures.
- Add configurable suppression for planned source outages/maintenance windows.
- Correlate freshness breaches with parser drift events when possible.

## Acceptance Criteria
1. Freshness regressions trigger alerts based on configured age thresholds.
2. Alert payload includes source and last-success metadata for triage.
3. Freshness breach events are retained for trend analysis.
4. Planned maintenance suppression does not hide unscheduled regressions.

## Validation
- Simulated stale-source scenarios for warning and critical thresholds.
- Payload verification test for freshness context fields.
- Suppression-path test for planned maintenance windows.

## Deliverables
- Freshness computation and alerting logic.
- Breach event records and query support.
- Tests for threshold, suppression, and payload correctness.
