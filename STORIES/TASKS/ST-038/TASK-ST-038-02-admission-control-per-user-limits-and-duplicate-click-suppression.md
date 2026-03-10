# Admission Control: Per-User Limits and Duplicate-Click Suppression

**Task ID:** TASK-ST-038-02  
**Story:** ST-038  
**Bucket:** backend  
**Requirement Links:** ST-038 Scope (bounded admission controls), ST-038 Acceptance Criteria #2 and #3, FR-4, NFR-1

## Objective

Implement bounded admission-control rules for resident-triggered processing requests while preserving meeting-level dedupe as the primary safeguard.

## Scope

- Enforce configurable per-user ceilings for active and queued on-demand requests.
- Implement duplicate-click suppression semantics that return deterministic API outcomes.
- Define error/limit responses that frontend clients can render consistently.
- Out of scope: frontend interaction copy, replay handling after terminal failures, and worker concurrency changes.

## Inputs / Dependencies

- TASK-ST-038-01 active-work dedupe identity.
- TASK-ST-037-01 request/status response contract.
- Existing configuration and settings patterns for runtime policy knobs.

## Implementation Notes

- Meeting-level dedupe should win before user-limit rejection when the same meeting is already active.
- Keep policy thresholds configurable and observable.
- Avoid exposing low-level queue internals in resident-facing outcomes.

## Acceptance Criteria

1. Resident-triggered requests are bounded by configurable admission limits. (ST-038 AC #2)
2. Duplicate clicks for the same active meeting produce deterministic non-duplicating outcomes. (ST-038 AC #3)
3. Limit responses are specific enough for frontend state handling without leaking queue internals.

## Validation

- Integration tests for limit-hit and duplicate-click cases.
- Settings tests for default and overridden admission-control values.
- Verify same-meeting repeat requests do not count as duplicate active jobs.

## Deliverables

- Admission-control policy implementation.
- Deterministic duplicate-click and limit response semantics.
- Integration/settings coverage for policy behavior.
