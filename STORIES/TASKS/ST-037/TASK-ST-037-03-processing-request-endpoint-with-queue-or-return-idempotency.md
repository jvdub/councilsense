# Processing-Request Endpoint with Queue-or-Return Idempotency

**Task ID:** TASK-ST-037-03  
**Story:** ST-037  
**Bucket:** backend  
**Requirement Links:** ST-037 Scope (processing-request endpoint), ST-037 Acceptance Criteria #3 and #4, FR-4, NFR-4

## Objective

Implement an authenticated processing-request endpoint that creates on-demand work or returns the existing active work item for the same discovered meeting.

## Scope

- Implement authenticated request handling for a discovered meeting.
- Return an existing active request instead of creating duplicate active work for the same meeting.
- Enforce city scoping and stable response semantics for newly queued vs already-active results.
- Out of scope: admission-control thresholds, terminal retry rules, and frontend messaging.

## Inputs / Dependencies

- TASK-ST-037-01 contract for request/response semantics.
- TASK-ST-036-03 discovered-meeting persistence and reconciliation.
- Existing auth/profile-based city scoping from ST-006.

## Implementation Notes

- Keep request semantics idempotent at the meeting level.
- Avoid coupling endpoint correctness to any single frontend behavior.
- Treat duplicate active work detection as a contract guarantee here, with policy hardening deferred to ST-038.

## Acceptance Criteria

1. Repeated requests for the same active meeting return the same active-work outcome instead of creating more work. (ST-037 AC #3)
2. Home-city scoping is enforced for processing requests. (ST-037 AC #4)
3. Response payloads distinguish newly queued requests from existing-active requests without ambiguity.

## Validation

- Integration tests for first request vs repeated request behavior.
- Scope-enforcement tests for off-city access attempts.
- Fixture coverage for discovered-only and already-linked local meeting cases.

## Deliverables

- Authenticated processing-request endpoint.
- Queue-or-return idempotent request behavior.
- Integration tests for active-request reuse and scope enforcement.
