# Notification Settings Toggles and Persistence

**Task ID:** TASK-ST-008-02  
**Story:** ST-008  
**Bucket:** frontend  
**Requirement Links:** MVP §4.4(2-3), FR-2, FR-5(4-5)

## Objective
Implement settings controls for notification enable/disable and pause/resume with persisted state across sessions.

## Scope (+ Out of scope)
- Build controls for notification on/off and pause/unpause window.
- Persist and rehydrate settings from backend profile/settings endpoints.
- Reflect current setting state on page load.
- Out of scope: push subscription registration flow.

## Inputs / Dependencies
- Authenticated settings surface from earlier stories.
- Backend settings endpoints.

## Implementation Notes
- Keep controls explicit and reversible.
- Prevent ambiguous mixed states in UI copy/labels.
- Exclude any email-channel controls from UI.

## Acceptance Criteria
1. Users can enable/disable notifications and pause/resume delivery.
2. Settings persist across sessions and page reloads.
3. UI includes push controls only for MVP notification channels.

## Validation
- Run frontend integration tests for toggle interactions and persisted reload.
- Manual verification across sign-out/sign-in cycle.

## Deliverables
- Settings UI components and persistence wiring.
- Tests covering toggle and pause/resume persistence.
