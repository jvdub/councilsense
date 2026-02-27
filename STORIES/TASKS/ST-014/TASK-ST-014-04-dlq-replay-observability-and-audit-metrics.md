# DLQ and Replay Observability with Measurable Outputs

**Task ID:** TASK-ST-014-04  
**Story:** ST-014  
**Bucket:** ops  
**Requirement Links:** NFR-4, ST-014 Acceptance Criteria #2

## Objective
Expose DLQ and replay operational metrics and dashboards with measurable hardening outputs.

## Scope
- Add metrics for DLQ inflow/backlog/age and replay outcomes.
- Add dashboard panels and basic alerts for abnormal backlog growth.
- Publish operational definitions for replay success and duplicate replay rate.
- Out of scope: changing replay business logic.

## Inputs / Dependencies
- TASK-ST-014-03 replay events and audit metadata.
- Existing observability stack from ST-011.

## Implementation Notes
- Minimum measurable outputs:
  - DLQ backlog count
  - DLQ oldest age
  - replay success rate
  - replay failure rate
  - replay duplicate-prevention hit count
- Tag metrics by city/source/channel where available.

## Acceptance Criteria
1. Operators can see DLQ volume, age, and replay outcomes in dashboards.
2. Replay success rate is computable from emitted metrics.
3. DLQ backlog growth warning threshold is documented and active.
4. Dashboard includes links to replay audit evidence.

## Validation
- Smoke test metric emission in staging.
- Dashboard panel query validation with seeded DLQ/replay events.
- Alert simulation for backlog threshold breach.

## Deliverables
- Metrics instrumentation and dashboard definitions.
- Alert rule config for DLQ backlog warning.
- Runbook snippet defining metric interpretation and response.
