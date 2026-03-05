# Structured Log Correlation Context for Multi-Document Pipeline

**Task ID:** TASK-ST-031-01  
**Story:** ST-031  
**Bucket:** ops  
**Requirement Links:** ST-031 Acceptance Criteria #1, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective
Add and validate required structured log fields for multi-document correlation across ingest, extract, compose, summarize, and publish stages.

## Scope
- Define required correlation fields (city/meeting/run/stage/source/artifact and related identifiers).
- Ensure stage-level log emission includes consistent field naming and value semantics.
- Define missing-field detection checks for observability contract compliance.
- Out of scope: metrics dashboard creation and alert threshold routing.

## Inputs / Dependencies
- Existing observability/logging conventions in backend services.
- AGENDA_PLAN §7 correlation field expectations.
- ST-029 multi-document processing context assumptions.

## Implementation Notes
- Prefer additive structured fields and preserve existing log consumers.
- Ensure identifiers align with replay and incident triage workflows.
- Treat absent required fields as observability contract failures.

## Acceptance Criteria
1. Structured logs include required correlation fields for multi-document troubleshooting.
2. Field names and value semantics are consistent across pipeline stages.
3. Missing-field cases are detectable via explicit validation checks.
4. Existing log flows remain backward compatible for current consumers.

## Validation
- Execute representative pipeline runs and inspect structured logs by stage.
- Verify required field presence for success and failure paths.
- Confirm stable correlation linking across run_id and artifact/source dimensions.

## Deliverables
- Structured logging field contract.
- Stage coverage matrix for required fields.
- Validation evidence for correlation completeness.
