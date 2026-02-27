# Smoke Validation and Triage Runbook

**Task ID:** TASK-ST-011-05  
**Story:** ST-011  
**Bucket:** docs  
**Requirement Links:** NFR-4

## Objective
Provide operational smoke checks and a concise triage runbook for baseline observability readiness.

## Scope
- In scope:
  - Non-local smoke checklist confirming logs and metrics ingestion.
  - Triage steps for top failure modes in pipeline and notifications.
  - Minimum evidence package for launch readiness.
- Out of scope:
  - Automated alert tuning and escalation policy hardening.

## Inputs / Dependencies
- TASK-ST-011-04

## Implementation Notes
- Keep runbook short and action-oriented.
- Map each failure mode to log query and dashboard panel.
- Include expected evidence retention location.

## Acceptance Criteria
1. Smoke checklist verifies telemetry present in target environment.
2. Runbook includes at least pipeline failure, notification failure, and stale source triage.
3. Team can execute runbook end-to-end during a rehearsal.

## Validation
- Execute smoke checklist in staging environment.
- Perform one rehearsal incident drill and document outcomes.

## Deliverables
- Runbook document.
- Smoke checklist document.
- Rehearsal evidence notes.
