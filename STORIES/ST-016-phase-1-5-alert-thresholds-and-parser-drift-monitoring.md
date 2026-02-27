# Phase 1.5: Alert Thresholds + Parser Drift Monitoring

**Story ID:** ST-016  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** FR-7(2), NFR-4 (alert thresholds), Phase 1.5 (§9)

## User Story
As an operator, I want actionable alerts and parser drift monitoring so reliability and quality regressions are detected before user impact grows.

## Scope
- Define and implement alert thresholds for ingestion failures, latency, and notification delivery errors.
- Implement parser/source drift detection signals tied to versioned parser metadata.
- Add triage runbook links and ownership for alert classes.

## Acceptance Criteria
1. Alert thresholds exist for ingestion failure rate, processing latency, and notification errors.
2. Parser version changes are recorded and drift events are detectable over time.
3. Source freshness regressions trigger operational warnings.
4. Alerts include sufficient metadata for triage (city/source/run identifiers).
5. Alert and drift signals are visible in hardening dashboards.

## Implementation Tasks
- [ ] Implement metrics-based alerts for failure and latency thresholds.
- [ ] Implement parser/source drift event recording and queryable views.
- [ ] Add source freshness alerting based on last-success age thresholds.
- [ ] Publish triage runbooks and ownership mapping for each alert class.
- [ ] Add synthetic/controlled tests to validate alert triggering behavior.

## Dependencies
- ST-010
- ST-011
- ST-015

## Definition of Done
- Hardening alerts and drift signals are live and tested.
- On-call/operator team can triage using linked runbooks.
- Reliability and quality regressions become proactively detectable.
