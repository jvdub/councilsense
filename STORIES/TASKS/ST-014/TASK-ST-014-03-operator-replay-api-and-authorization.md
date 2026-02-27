# Operator Replay API and Authorization

**Task ID:** TASK-ST-014-03  
**Story:** ST-014  
**Bucket:** backend  
**Requirement Links:** FR-5, NFR-4, ST-014 Acceptance Criteria #3

## Objective
Provide an authorized operator action to replay eligible DLQ messages with audit trail and safe requeue behavior.

## Scope
- Implement replay endpoint/tool for DLQ items.
- Validate replay eligibility and prevent invalid replays.
- Write audit records for replay actor, reason, and outcome.
- Out of scope: dashboards and synthetic test suites.

## Inputs / Dependencies
- TASK-ST-014-01 DLQ data model.
- TASK-ST-014-02 retry policy configuration.
- Existing operator authN/authZ controls.

## Implementation Notes
- Use replay idempotency key to prevent double requeue.
- Restrict replay of permanently-invalid payloads unless override policy allows.
- Record source DLQ item and new queue item correlation IDs.

## Acceptance Criteria
1. Authorized operator can replay eligible DLQ entries.
2. Replay creates auditable linkage between DLQ record and requeued message.
3. Unauthorized replay attempts are denied and logged.
4. Replay action cannot bypass idempotency protections.

## Validation
- API integration tests for authorized and unauthorized actors.
- Replay eligibility tests (eligible/ineligible paths).
- Audit trail test ensuring actor, timestamp, and correlation IDs are stored.

## Deliverables
- Replay endpoint/tooling implementation.
- Authorization policy update for replay action.
- Audit log/event schema extensions and tests.
