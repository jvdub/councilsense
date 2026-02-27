# Push Subscribe/Unsubscribe UX

**Task ID:** TASK-ST-008-03  
**Story:** ST-008  
**Bucket:** frontend  
**Requirement Links:** MVP §4.4(4-5), FR-5(4-5), NFR-3

## Objective
Implement browser push subscription and unsubscription UX, including permission prompts and graceful degradation.

## Scope (+ Out of scope)
- Add service worker registration and PushManager-based subscribe/unsubscribe flows.
- Handle permission states (granted, denied, default) in UI.
- Handle unsupported-browser messaging with non-blocking fallback.
- Out of scope: backend delivery fanout logic.

## Inputs / Dependencies
- TASK-ST-008-01 discovery outcomes.
- TASK-ST-008-02 settings context for surface placement.

## Implementation Notes
- Keep user intent explicit before requesting permission.
- Ensure unsubscribe path is always available when subscribed.
- Separate unsupported-browser and denied-permission states in UX.

## Acceptance Criteria
1. User can subscribe current browser for push when supported.
2. User can unsubscribe current browser later.
3. Unsupported/denied states are clearly communicated with recovery guidance.

## Validation
- Run frontend tests with mocked permission/capability states.
- Manual browser smoke checks for subscribe and unsubscribe.

## Deliverables
- Push subscription UI flow and service worker integration points.
- Test coverage for permission and capability branches.
