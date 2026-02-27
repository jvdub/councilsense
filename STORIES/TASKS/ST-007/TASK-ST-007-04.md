# Notification Deep-Link Routing to Meeting Detail

**Task ID:** TASK-ST-007-04  
**Story:** ST-007  
**Bucket:** frontend  
**Requirement Links:** MVP §4.5(3), FR-4

## Objective
Support deep-link navigation from notification URLs containing `meeting_id` to the correct meeting detail page.

## Scope (+ Out of scope)
- Parse/handle meeting_id from supported notification URL entry points.
- Route user to `/meetings/[meetingId]` detail view.
- Provide graceful fallback for invalid/missing meeting IDs.
- Out of scope: notification delivery backend behavior.

## Inputs / Dependencies
- TASK-ST-007-03.
- Notification URL format from ST-009 integration assumptions.

## Implementation Notes
- Keep routing logic minimal and deterministic.
- Reuse existing detail page error handling for invalid IDs.
- Avoid introducing additional navigation surfaces.

## Acceptance Criteria
1. Valid deep link opens intended meeting detail page.
2. Invalid deep link does not break navigation flow.
3. Behavior is consistent for authenticated users.

## Validation
- Run route-level tests for deep-link parsing and navigation.
- Manual smoke check via direct URL entry with meeting_id.

## Deliverables
- Deep-link route handling logic and tests.
