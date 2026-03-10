# Reader API Payload Design for Discovered Meetings and Processing Status

**Task ID:** TASK-ST-037-01  
**Story:** ST-037  
**Bucket:** backend  
**Requirement Links:** ST-037 Scope (status fields and discovered-meeting projection), ST-037 Acceptance Criteria #1 and #2, FR-4, FR-6

## Objective

Define the additive reader API contract that projects discovered meetings and a stable set of user-visible processing states.

## Scope

- Define additive list payload fields for discovered-meeting metadata and processing-state projection.
- Freeze a user-visible status model that distinguishes discovered, queued, processing, processed, and failed states.
- Define request endpoint response semantics for newly queued vs existing active work.
- Out of scope: query implementation, admission-control policies, and frontend rendering.

## Inputs / Dependencies

- ST-036 discovered-meeting registry and reconciliation model.
- Existing meetings list/detail API contracts from ST-006.
- Story-level requirements for additive processing-request behavior.

## Implementation Notes

- Keep the new fields additive and compatible with existing processed-meeting consumers.
- Favor stable response semantics that do not leak internal queue details.
- Ensure status definitions are explicit enough for frontend tile-state rendering.

## Acceptance Criteria

1. The list payload contract can represent both discovered-only and processed meetings. (ST-037 AC #1)
2. User-visible status values are frozen and unambiguous. (ST-037 AC #2)
3. Request-response semantics distinguish newly created work from already-active work without requiring client inference.

## Validation

- Contract fixture review for discovered, active, processed, and failed examples.
- Confirm additive compatibility against current meetings list consumers.
- Validate that response semantics are specific enough for frontend action handling.

## Deliverables

- Additive reader API contract for discovered-meeting projection.
- Status model and processing-request outcome contract.
- Representative contract fixtures for downstream backend/frontend tasks.
