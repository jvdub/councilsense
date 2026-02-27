# Alert Rules for Ingestion Failures, Latency, and Notification Errors

**Task ID:** TASK-ST-016-02  
**Story:** ST-016  
**Bucket:** ops  
**Requirement Links:** FR-7(2), NFR-4, ST-016 Acceptance Criteria #1 and #4

## Objective
Implement actionable alert rules for core reliability failure classes with required triage metadata.

## Scope
- Add alert rules for ingestion failure rate.
- Add alert rules for processing latency thresholds.
- Add alert rules for notification delivery error rates.
- Ensure alerts include city/source/run identifiers where available.
- Out of scope: parser drift-specific event generation.

## Inputs / Dependencies
- TASK-ST-016-01 threshold matrix.
- Existing metrics pipeline and alerting platform.

## Implementation Notes
- Include warning/critical severities where matrix defines them.
- Add silence windows or rate-limiting only if required to reduce noise.
- Track alert fire count and acknowledgment metadata for tuning.

## Acceptance Criteria
1. Alerts trigger at configured thresholds for all three classes.
2. Alert payloads include triage metadata required by runbook.
3. Alert ownership and escalation follow configured mapping.
4. Rules are environment-configurable and documented.

## Validation
- Controlled metric injection to trigger each alert class.
- Payload inspection test for metadata completeness.
- Escalation path test for owner routing.

## Deliverables
- Alert rule definitions and deployment config.
- Metadata mapping for alert payload fields.
- Test evidence for triggered alerts per class.
