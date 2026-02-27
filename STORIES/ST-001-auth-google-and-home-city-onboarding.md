# Managed Auth + Home City Onboarding

**Story ID:** ST-001  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.1, FR-1, FR-2, FR-6, NFR-3, NFR-5

## User Story
As a new resident user, I want to sign in with Google and set my home city so I can receive relevant meeting updates.

## Scope
- Integrate managed auth (Cognito + Google) for web sign-in/sign-out.
- Implement first-run onboarding flow requiring home city selection.
- Enforce valid city selection from configured city list.
- Enforce user-scoped authorization for profile bootstrap endpoints.

## Acceptance Criteria
1. User can sign in via Google using managed auth and establish a secure session.
2. First-time authenticated user without `home_city_id` is redirected to onboarding.
3. Onboarding city selection accepts only configured cities.
4. Returning authenticated user with `home_city_id` bypasses onboarding.
5. Google is the only enabled social provider in MVP auth configuration.
6. Localhost OAuth redirects function in development config.

## Implementation Tasks
- [ ] Configure Cognito/Amplify auth with Google provider and environment-specific callback URLs.
- [ ] Add backend auth validation middleware and user bootstrap logic.
- [ ] Build onboarding city selection UI and submit flow.
- [ ] Add backend validation to reject unsupported city IDs.
- [ ] Add auth/onboarding integration tests for first-time and returning users.

## Dependencies
- None

## Definition of Done
- Auth and onboarding flow works end-to-end locally and in cloud dev environment.
- Access controls prevent users from writing other users’ profile data.
- Automated tests cover happy path and invalid city cases.
