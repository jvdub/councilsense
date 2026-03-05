# Agenda Plan: Multi-Document Observability, Alerts, and Runbook Completion

**Story ID:** ST-031  
**Phase:** Phase 4 (Operations and reliability)  
**Requirement Links:** AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §6 Testing and validation plan, AGENDA_PLAN §8 Risks and mitigations

## User Story
As an on-call engineer, I want source-aware metrics, alerts, and runbooks so multi-document pipeline incidents are detected and resolved quickly.

## Scope
- Extend structured logging dimensions for city/meeting/run/stage/source/artifact context from AGENDA_PLAN section "Observability, operations, and runbook updates".
- Add metrics and alerts for ingest/extract/compose failures, coverage/precision quality indicators, parser drift, and DLQ backlog from AGENDA_PLAN section "Observability, operations, and runbook updates".
- Update runbooks for triage, replay, confidence policy, and rollback workflows aligned to document-aware operations.

## Acceptance Criteria
1. Structured logs include required correlation fields for multi-document troubleshooting.
2. Dashboards expose source-type outcomes, coverage ratio, citation precision ratio, and DLQ backlog/age.
3. Alerts fire for parser drift spikes, missing-minutes surges, summarize failure spikes, and stale DLQ backlog.
4. Runbooks include updated triage, replay, and rollback procedures with clear ownership.
5. Alert simulation and runbook walkthroughs pass in staging.

## Implementation Tasks
- [ ] Add/validate structured log fields and correlation IDs across pipeline stages.
- [ ] Implement metrics instrumentation and dashboard panels for new gate/coverage indicators.
- [ ] Configure alert thresholds/routes for drift, failure spikes, and DLQ health.
- [ ] Update runbook documents and incident response checklists.
- [ ] Execute staging alert simulations and capture follow-up actions.

## Dependencies
- ST-011
- ST-016
- ST-029
- ST-030

## Definition of Done
- Multi-document pipeline observability is complete with actionable alerting.
- Operators can triage and remediate incidents using updated runbooks.
- Staging simulations confirm alert and runbook effectiveness.
