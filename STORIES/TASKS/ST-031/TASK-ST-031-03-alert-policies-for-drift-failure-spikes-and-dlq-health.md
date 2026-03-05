# Alert Policies for Drift, Failure Spikes, and DLQ Health

**Task ID:** TASK-ST-031-03  
**Story:** ST-031  
**Bucket:** ops  
**Requirement Links:** ST-031 Acceptance Criteria #3, AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §8 Risks and mitigations

## Objective
Define and configure alert rules, thresholds, and routes for parser drift, missing-minutes surges, summarize failures, and stale DLQ backlog.

## Scope
- Define alert conditions and threshold baselines for required incident classes.
- Configure severity levels, deduplication, and routing/escalation targets.
- Define alert payload fields needed for immediate triage context.
- Out of scope: runbook procedure authoring and simulation execution evidence.

## Inputs / Dependencies
- TASK-ST-031-01 structured correlation fields.
- TASK-ST-031-02 metrics and dashboards for signal sources.
- Existing on-call routing, paging, and escalation policy conventions.

## Implementation Notes
- Keep thresholds adjustable per environment with clear defaults.
- Ensure alerts are actionable and include run/source identifiers.
- Minimize alert noise via dedupe windows and sustained-condition checks.

## Acceptance Criteria
1. Alerts fire for parser drift spikes, missing-minutes surges, summarize failure spikes, and stale DLQ backlog.
2. Alert rules include documented threshold values and severity routing.
3. Alert payloads include context needed to jump to diagnostics and dashboards.
4. False-positive noise controls are defined and validated.

## Validation
- Simulate each incident class and verify alert trigger and route behavior.
- Confirm payload completeness for triage handoff.
- Validate dedupe/suppression behavior under repeated failures.

## Deliverables
- Alert policy specification with threshold matrix.
- Routing/escalation mapping and ownership table.
- Alert simulation checklist and preliminary results.
