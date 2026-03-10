# Runbook Updates for Triage, Replay, Confidence, and Rollback

**Task ID:** TASK-ST-031-04  
**Story:** ST-031  
**Bucket:** docs  
**Requirement Links:** ST-031 Acceptance Criteria #4, AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §8 Risks and mitigations

## Objective

Update runbooks with multi-document triage, replay, confidence-policy, and rollback procedures including explicit ownership.

## Scope

- Update incident triage flow for source-aware failures and quality-signal regressions.
- Add replay procedure guidance with actor, reason, idempotency key, and outcome capture.
- Add confidence-policy and rollback decision trees aligned to enforcement controls.
- Out of scope: changing alert thresholds or adding new telemetry sources.

## Inputs / Dependencies

- TASK-ST-031-02 dashboard panels and metric definitions.
- TASK-ST-031-03 alert policy and route mappings.
- Existing runbook templates and ownership conventions under docs/runbooks.

## Implementation Notes

- Keep procedure steps executable and command-ready for on-call responders.
- Include clear ownership, escalation path, and handoff expectations.
- Align confidence-policy language with limited-confidence publish semantics.

## Acceptance Criteria

1. Runbooks include updated triage, replay, and rollback procedures for document-aware operations.
2. Procedures include clear owner roles and escalation paths.
3. Replay and confidence-policy steps capture required audit metadata.
4. Runbook content maps directly from alert classes to remediation actions.

## Validation

- Conduct runbook walkthrough with representative incident scenarios.
- Verify each alert class links to a single primary runbook entry point.
- Confirm procedural completeness with operations/release-owner review.

## Deliverables

- Updated runbook sections and ownership matrix.
- Incident-response checklist updates.
- Walkthrough sign-off notes and open-action list.
