# Baseline Dashboards

**Task ID:** TASK-ST-011-04  
**Story:** ST-011  
**Bucket:** ops  
**Requirement Links:** NFR-4

## Objective
Create MVP dashboards for ingestion and notification health using the standardized telemetry.

## Scope
- In scope:
  - Pipeline success/failure and duration panels.
  - Notification enqueue/send/retry/failure panels.
  - Source-level freshness and failure snapshot panel.
- Out of scope:
  - Advanced anomaly detection or paging policies.

## Inputs / Dependencies
- TASK-ST-011-02
- TASK-ST-011-03
- ST-010 source health signals

## Implementation Notes
- Prefer small panel set that answers what failed, where, when.
- Include default time window and environment filters.
- Keep panel queries simple and maintainable.

## Acceptance Criteria
1. Dashboard shows ingestion and notification baseline health.
2. Operators can identify failing stage and impacted city/source.
3. Dashboard config is version-controlled.

## Validation
- Run dashboard query sanity checks against seeded telemetry.
- Manual smoke: induce one pipeline and one notification failure and verify visibility.

## Deliverables
- Dashboard configuration files.
- Query definitions for each panel.
- Screenshot or exported evidence artifact.
