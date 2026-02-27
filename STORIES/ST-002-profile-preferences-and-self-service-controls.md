# Profile Preferences + Self-Service Controls

**Story ID:** ST-002  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.1(4), MVP §4.4(4), FR-2, FR-5(4), FR-6, NFR-3

## User Story
As an authenticated user, I want to edit my home city and notification preferences so my app experience and alerts stay relevant.

## Scope
- Implement profile read/update endpoints for home city and notification settings.
- Implement pause/unpause behavior for notifications.
- Ensure user can only read/write own profile/preferences.

## Acceptance Criteria
1. User can view current profile state (`email`, `home_city_id`, notification settings).
2. User can update home city to another valid configured city.
3. User can enable/disable notifications and set/remove pause window.
4. Changes are applied only to the authenticated user identity.
5. Downstream notification fan-out excludes users with `notifications_enabled=false` or active pause window.

## Implementation Tasks
- [ ] Implement `GET /v1/me` and `PATCH /v1/me` with request validation.
- [ ] Add authorization policy enforcing self-only updates.
- [ ] Add preference model fields and migration alignment if missing.
- [ ] Wire frontend settings form for city and notification preference edits.
- [ ] Add integration tests for authz, validation, and pause/unpause transitions.

## Dependencies
- ST-001

## Definition of Done
- Profile and preference updates persist and are reflected in UI and API responses.
- Access control tests prove self-only behavior.
- Notification pause/unsubscribe state is available to notification pipeline.
