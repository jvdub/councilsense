# CouncilSense — Frontend Plan

## 1) Scope and MVP outcomes

This plan defines the single frontend implementation path for MVP, aligned to product requirements and backend/database contracts.

**In scope (MVP):**
- Managed auth with Google (Cognito/Amplify).
- Onboarding to set one home city; later edit in settings.
- Home-city meetings list and meeting detail.
- Evidence-grounded meeting rendering, including `limited_confidence`.
- Push preferences: enable/disable, pause/resume, subscribe/unsubscribe browser device.
- Robust loading/error/empty states and pragmatic test coverage.
- Local-first and AWS Amplify deployment parity.

**Out of scope (MVP):**
- Multi-city follow per user.
- Q&A/chat UI.
- Email/SMS channels.
- Advanced personalization.

---

## 2) Conflict resolution decisions (final)

1. **Route shape**
   - Decision: use clean public routes + authenticated app routes **without `/app` prefix**.
   - Final routes: `/`, `/auth/sign-in`, `/auth/callback`, `/onboarding/city`, `/meetings`, `/meetings/[meetingId]`, `/settings`.
   - Why: simpler UX URLs while preserving route-group isolation in App Router.

2. **Data strategy**
   - Decision: **server-first rendering** for meetings pages + **TanStack Query** for client mutations/revalidation.
   - Why: combines fast initial paint/readability with reliable client-side preference and push workflows.

3. **API contract typing**
   - Decision: typed `apiClient` with runtime validation (`zod`) now; OpenAPI generation can replace internals later.
   - Why: protects MVP from contract drift immediately without blocking on full backend spec generation.

4. **State management**
   - Decision: no global app store in MVP.
   - Why: URL state + React local state + query cache is sufficient and lower maintenance.

5. **Push UX depth**
   - Decision: explicit capability detection and recovery actions for `invalid | expired | suppressed`.
   - Why: required for practical browser variance and requirement-aligned pause/unsubscribe behavior.

---

## 3) Information architecture and routes

## Public/Auth
- `/` — landing + primary sign-in CTA.
- `/auth/sign-in` — managed sign-in entry.
- `/auth/callback` — OAuth callback handler.

## Onboarding
- `/onboarding/city` — required home city selection for first-run users.

## Authenticated app
- `/meetings` — city-scoped meetings list (home city only).
- `/meetings/[meetingId]` — detail with summary, decisions, topics, evidence.
- `/settings` — profile + notification preferences + push subscription management.

## Route guard behavior
- Unauthenticated access to authenticated routes redirects to `/auth/sign-in`.
- Authenticated users missing `home_city_id` redirect to `/onboarding/city`.
- Authenticated users with home city land on `/meetings`.

---

## 4) Component architecture

## Shell
- `AppShell` (server): app chrome, top navigation, city context.
- `TopNav` (client-lite): meetings/settings navigation and sign-out.

## Onboarding
- `CitySelectForm` (client): choose from supported cities and submit `PATCH /v1/me`.
- `OnboardingCityPage` (server wrapper): guard + initial city options fetch.

## Meetings list/detail
- `MeetingListPage` (server): initial list fetch and pagination cursor handoff.
- `MeetingCard` (server): title/date/status/summary preview.
- `MeetingDetailPage` (server): base detail fetch.
- `SummarySection`, `DecisionsSection`, `TopicsSection` (server).
- `EvidencePanel` (server/client progressive disclosure).
- `ConfidenceBanner` (server): explicit `limited_confidence` presentation.

## Settings/notifications
- `SettingsPage` (server): bootstrap profile and subscription state.
- `HomeCityForm` (client).
- `NotificationToggle` (client): enabled/disabled.
- `NotificationPauseForm` (client): pause until timestamp + resume.
- `PushSubscriptionManager` (client): subscribe/unsubscribe and status recovery actions.

## Shared states
- `LoadingState`, `ErrorState`, `EmptyState`, `NotFoundState`.

---

## 5) Data-fetch and client contract approach

## Frontend API boundary
All network access goes through `src/lib/api`:
- `client.ts` (auth header propagation, timeout, normalized errors).
- `schemas.ts` (`zod` request/response validators).
- `endpoints.ts` (typed resource functions).

## Core endpoint usage
- `GET /v1/me`
- `PATCH /v1/me` (`home_city_id`, `notifications_enabled`, `notifications_paused_until`)
- `GET /v1/cities/{city_id}/meetings?cursor&limit&status`
- `GET /v1/meetings/{meeting_id}`
- `GET /v1/meetings/{meeting_id}/evidence`
- `POST /v1/me/push-subscriptions`
- `GET /v1/me/push-subscriptions`
- `DELETE /v1/me/push-subscriptions/{subscription_id}`

## Rendering/caching model
- Meetings list/detail: server fetch for first render; optional client revalidation.
- Settings and push actions: client components + TanStack Query mutations.
- Query invalidation is narrow (resource-scoped only).
- Cursor pagination for meetings list.

## Contract rules
- Treat backend as source of truth for status fields and confidence labels.
- Fail closed on invalid payload shape (recoverable UI error + retry).
- Map backend errors to stable user-facing categories (auth, validation, network, permission, unknown).

---

## 6) UX states (loading/error/empty)

## Loading
- Route-level skeletons for `/meetings`, `/meetings/[meetingId]`, `/settings`.
- Section-level loading for evidence and subscription status.

## Error
- Route-level `error.tsx` boundaries for fatal page load failures.
- Section-level recoverable cards with retry CTA for partial failures.
- If evidence fetch fails, keep summary/decisions/topics visible and show evidence-specific error.

## Empty
- Meetings list empty: “No meetings available yet for your city.”
- Evidence empty: “No evidence snippets available for this claim.”
- No push subscription: actionable “Enable push on this device.”

## Confidence handling
- `processed`: standard presentation.
- `limited_confidence`: persistent banner and toned certainty language; still render available evidence.

---

## 7) Push preferences and unsubscribe behavior

1. Capability check (`serviceWorker`, `PushManager`) before showing subscribe action.
2. Permission requested only on explicit user action.
3. Successful subscription posts endpoint/key payload to backend.
4. Unsubscribe removes backend subscription and browser subscription object.
5. Pause/resume is profile-level and independent of per-device subscription records.
6. UI handles backend states:
   - `active`: healthy.
   - `invalid`/`expired`: resubscribe CTA.
   - `suppressed`: explain suppression and recover via refresh subscription.
7. Double-submit prevention on all preference mutations.

---

## 8) Testing strategy (pragmatic)

## Unit
- API schema parsing and mapper logic.
- Confidence label rendering rules.
- Pause/unpause utility behavior.
- Push permission/capability mapping helpers.

## Component/integration (RTL + MSW)
- Onboarding happy path and validation failures.
- Meetings list: loading, empty, error, success.
- Meeting detail: processed vs limited-confidence rendering.
- Evidence partial-failure behavior.
- Settings mutations: toggle, pause, resume, city update, push add/remove.

## E2E smoke (Playwright)
- New user: sign-in → onboarding city → meetings list.
- Existing user: open detail and verify evidence/confidence UI.
- Settings: disable/pause/resume + subscription refresh flow.

## Contract safety
- Fixture-based contract tests for `/v1/me`, meetings list/detail, evidence, subscriptions.
- CI fails on required field/status drift.

---

## 9) Delivery plan

## Phase F0 (foundation)
- App Router route groups, auth guard, typed API client, env validation, baseline test harness.

## Phase F1 (auth + onboarding)
- `/`, `/auth/*`, `/onboarding/city`, profile bootstrap and redirect logic.

## Phase F2 (reader MVP)
- `/meetings`, `/meetings/[meetingId]`, confidence and evidence rendering, all UX states.

## Phase F3 (preferences + push)
- `/settings`, notification toggles/pause/resume, push subscription lifecycle and recovery UX.

## Phase F4 (hardening)
- Contract drift checks, accessibility polish, observability hooks, regression suite stabilization.

---

## 10) Deployment plan (local + AWS)

## Local
- Next.js app with env-driven config:
  - `NEXT_PUBLIC_AWS_REGION`
  - `NEXT_PUBLIC_COGNITO_USER_POOL_ID`
  - `NEXT_PUBLIC_COGNITO_CLIENT_ID`
  - `NEXT_PUBLIC_COGNITO_DOMAIN`
  - `NEXT_PUBLIC_API_BASE_URL`
  - `NEXT_PUBLIC_VAPID_PUBLIC_KEY`
- Same API contracts as cloud.
- Push may use test-equivalent flow when localhost/browser constraints apply.

## AWS
- Host frontend on Amplify.
- Configure per-environment variables (`dev`, `staging`, `prod`).
- Ensure HTTPS domain for service worker/push reliability.
- Configure allowed origins and CSP for Cognito + backend API.
- Enable build/runtime logs and release checks.

## Release gates
- Auth/onboarding flow passes.
- Meetings detail shows evidence and confidence state correctly.
- Pause/unsubscribe behavior persists across refresh and respects backend state.
- Contract and smoke tests pass in CI.

---

## 11) MVP frontend definition of done

MVP frontend is complete when:
1. User signs in with Google and sets home city on first run.
2. Returning user lands on home-city meetings list.
3. Meeting detail shows summary, decisions, topics, and evidence pointers.
4. `limited_confidence` is clearly and consistently represented.
5. User can enable/disable notifications, pause/resume, and subscribe/unsubscribe push per device.
6. Loading/error/empty states are implemented for all MVP routes.
7. Local and AWS deployments run the same frontend code with configuration-only differences.