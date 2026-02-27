# Observability Baseline for Pipeline + Notifications

**Story ID:** ST-011  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** NFR-4, NFR-1, NFR-2

## User Story
As an operator, I want baseline dashboards and logs for ingestion and notification health so I can detect and triage failures quickly.

## Scope
- Implement structured logs for pipeline and notification lifecycle.
- Emit metrics for success/failure rates and latency.
- Provide MVP dashboard views for ingestion and notification health.

## Acceptance Criteria
1. Ingestion success/failure counts and processing duration are tracked.
2. Notification enqueue/send outcomes and failures are tracked.
3. Audit trail exists for source artifacts and summary generation timestamps.
4. Basic dashboard/log views for pipeline and notification health are available before pilot launch.
5. MVP baseline does not require full hardening alerts yet.

## Implementation Tasks
- [ ] Standardize structured log fields (city, meeting, run, dedupe key, outcome).
- [ ] Add metrics instrumentation for pipeline stages and notification delivery.
- [ ] Create baseline dashboard panels for ingestion and notifications.
- [ ] Add operational runbook notes for common failure triage.
- [ ] Add smoke validation that metrics/log streams are populated in non-local env.

## Dependencies
- ST-004
- ST-009
- ST-010

## Definition of Done
- Operators can answer “what failed, where, and when” for pilot operations.
- Baseline operational visibility satisfies MVP exit criterion.
- Runbook links are available to the delivery team.
