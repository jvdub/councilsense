# Alert Threshold Baseline and Ownership Discovery

**Task ID:** TASK-ST-016-01  
**Story:** ST-016  
**Bucket:** ops  
**Requirement Links:** FR-7(2), NFR-4

## Objective
Define initial alert thresholds, severity mapping, and owner routing for ingestion failures, latency, notification errors, and freshness signals.

## Scope
- Establish baseline thresholds and severities per alert class.
- Define ownership/on-call routing for each class.
- Document triage metadata requirements (city/source/run IDs).
- Out of scope: implementing alert rules or parser drift storage.

## Inputs / Dependencies
- Historical operational metrics and incident notes (if available).
- Existing observability conventions from ST-011.

## Implementation Notes
- Capture rationale for each threshold and expected false-positive tolerance.
- Mark provisional thresholds for post-launch tuning review.
- Ensure output can be translated directly into alert rule config.

## Acceptance Criteria
1. Threshold matrix exists for ingestion failures, latency, notification errors, and freshness.
2. Each alert class has owner, severity, and escalation policy.
3. Required triage metadata fields are explicitly defined.
4. Open operational unknowns are tracked with owner and due date.

## Validation
- Ops and engineering review completed.
- Dry-run threshold backtest on historical data window.
- Approval recorded for initial hardening rollout thresholds.

## Deliverables
- Alert threshold and ownership matrix.
- Escalation mapping document.
- Backtest summary with recommended threshold adjustments.
