# Notification Preferences + Push Subscriptions UI

**Story ID:** ST-008  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.4(2-5), FR-2, FR-5(4-5), NFR-3

## User Story
As a resident, I want to control notification settings and device push subscriptions so alerts are useful and not noisy.

## Scope
- Implement settings UI for notification enable/disable and pause/unpause.
- Implement browser push subscribe/unsubscribe flow.
- Reflect invalid/expired/suppressed subscription states with recovery actions.

## Acceptance Criteria
1. User can enable/disable notifications and pause/resume delivery in settings.
2. User can subscribe current browser to push and unsubscribe it later.
3. Invalid/expired/suppressed subscription states are visible and recoverable.
4. Notification settings persist across sessions.
5. Settings surface includes push controls only; email channel controls are explicitly out of MVP scope.

## Implementation Tasks
- [ ] Build settings controls for notification toggles and pause window.
- [ ] Integrate service worker + PushManager registration flow.
- [ ] Add subscription CRUD integration with backend endpoints.
- [ ] Implement UX for non-supporting browsers and denied permissions.
- [ ] Add integration tests for setting persistence and subscribe/unsubscribe flows.

## Dependencies
- ST-002
- ST-007

## Definition of Done
- Settings and push controls work in supported browsers and degrade gracefully otherwise.
- Backend subscription records reflect UI actions.
- Tests cover primary and recovery flows.
