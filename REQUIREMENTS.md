# CouncilSense — Product Requirements (Draft v0.4)

**Date:** 2026-02-26  
**Status:** Draft (reset baseline)  
**Goal:** Define the minimum product needed for: “Sign up, tell us what city you live in, and receive useful summaries of city government meetings,” while supporting both local operation and straightforward AWS deployment.

## 1) Product Vision

CouncilSense helps residents stay informed about local government by automatically summarizing city meetings and notifying people about important developments in their city.

## 2) Primary User Problem

Most residents do not have time to read long council packets/minutes but still want to know what happened in city government that affects daily life.

## 3) Target Users

- **Primary:** City residents who want concise updates from local government meetings.
- **Secondary (later):** Journalists, neighborhood groups, civic organizers.

## 4) MVP Scope (What must exist)

MVP is defined as the first end-to-end production slice that works reliably for one pilot city while keeping architecture and data models ready to scale to many configured cities.

### 4.1 User Account & Onboarding

1. User authentication is handled by a managed identity provider (no custom auth implementation).
2. MVP requires at least one social login provider (Google).
3. User can set a **home city** during onboarding.
4. User can edit home city later.

### 4.2 City Coverage

1. System supports a defined list of cities and is designed to scale to many configured cities.
2. MVP launches with one pilot city enabled by default, while keeping configuration and data models city-agnostic.
3. Each city has meeting sources configured by admin/dev team.
4. Meetings are linked to a city identifier.
5. Ingestion coverage is city-driven (configured city list), not strictly user-driven.
6. System may ingest cities with zero active subscribers so history is available when users join.

### 4.3 Meeting Ingestion & Processing

1. System ingests council meeting materials (agenda packet/minutes/transcript text where available).
2. System extracts structured meeting content.
3. System generates:
   - meeting summary (short)
   - key decisions / actions
   - notable topics
4. Claims in summaries should be evidence-grounded to source text.

### 4.4 User Notifications

1. User receives notification when new meeting summary is available for their city.
2. MVP notification channel: **push notifications** (PWA/web push or app push).
3. Notification includes:
   - city
   - meeting date/title
   - short summary
   - link to full meeting page in app
4. User can pause/unsubscribe notifications.
5. Email delivery is deferred to post-MVP as a fallback/digest channel.

### 4.5 Reader Experience

1. User can view a list of meetings for their city.
2. User can open a meeting detail page and read:
   - summary
   - key decisions
   - links/evidence snippets to source sections
3. Meeting Q&A is deferred to post-MVP.

## 5) Out of Scope for MVP

- Multi-city following per user (single home city only).
- SMS notifications.
- Real-time/live meeting alerts.
- Advanced personalization (topic tuning, strictness controls).
- Public API and third-party integrations.
- Enterprise/admin portal beyond minimal internal ops tools.

## 6) Functional Requirements (Detailed)

### FR-1 Authentication

- Authentication must use a managed provider (for example Cognito/Amplify Auth, Auth0, Clerk).
- MVP supports sign in with Google OAuth.
- Local development must support auth flows on localhost via configured OAuth redirect URIs.
- Sessions are secure and expire appropriately.

### FR-2 User Profile

- Profile stores: email, city, notification preference, created/updated timestamps.
- City value must be valid against supported city list.

### FR-3 Meeting Pipeline

- New city meeting input triggers processing pipeline.
- Pipeline stores raw artifacts + processed structured output.
- Pipeline marks status: pending, processed, failed.
- Pipeline can run on schedule for all configured cities, independent of signup counts.
- Pipeline should support priority tiers (for example: subscribed cities first, then full configured list).

### FR-4 Summarization Quality

- Every summary should include at least one evidence citation/snippet per key claim where possible.
- If evidence is weak/absent, system should state uncertainty instead of fabricating certainty.
- Citation output must follow a structured schema (source artifact ID, section/offset, excerpt).
- If minimum citation quality is not met, publish a limited-confidence result instead of a confident synthesized claim.

### FR-5 Notification Delivery

- On successful processing, all subscribed users in that city are queued for push notification.
- Delivery attempts and failures are logged (basic logs in MVP; expanded analytics in hardening).
- Notification sends must use a deterministic dedupe key (`user_id + meeting_id + notification_type`) to enforce idempotency.
- Retries use exponential backoff with a configurable max-attempt policy; exhausted attempts route to dead-letter handling in hardening phase.
- Invalid/expired push subscriptions are marked and suppressed from further sends until refreshed.

### FR-6 User Access Control

- User can only edit their own profile/preferences.
- Internal ingestion/admin actions are restricted (not public-facing).

### FR-7 Ingestion Resilience

- Each configured city source has health checks and last-success timestamps (minimum viable checks in MVP; expanded checks in hardening).
- Source/parser version used per processing run is recorded for reproducibility.
- If extraction confidence is below threshold, the meeting is flagged for manual review and user-facing outputs indicate limited confidence.
- Source failures degrade gracefully and do not block processing for other cities.

## 7) Non-Functional Requirements

### NFR-1 Reliability

- Ingestion failures should not crash the app; failed jobs are retryable.
- Notification sends are idempotent (avoid duplicate notifications for same meeting/user).

### NFR-2 Performance (MVP Targets)

- p95 end-to-end ingest-to-published latency is <= 30 minutes for pilot cities.
- p95 notification enqueue latency is <= 5 minutes after successful processing.
- p95 city meetings page load is < 2 seconds for normal dataset sizes.

### NFR-3 Security & Privacy

- If password auth is enabled later, passwords must be handled by the managed provider with modern best practice.
- Personal data limited to what is needed (email, city, preferences).
- Basic privacy policy and terms links present before launch.
- Data retention policy is defined and documented before pilot launch.
- User deletion requests remove or anonymize personal profile data within a defined SLA.

### NFR-4 Observability

- Track ingestion success/failures, processing duration, and notification delivery rates.
- Maintain audit trail of source artifacts and summary generation timestamps.
- MVP includes basic operational visibility; hardening defines alert thresholds for ingestion failure rate, processing latency, and notification delivery errors.
- Dead-letter queue volume and replay outcomes are visible in operational dashboards during hardening.

### NFR-5 Local-First + Cloud Portability

- The full product must run locally on a single machine for development/demo use.
- The same core services should deploy to AWS with minimal code branching.
- Environment-specific differences must be configuration-driven (not separate codebases).
- Frontend hosting should support AWS Amplify as the default cloud option.

### NFR-6 Cost & Operational Simplicity

- MVP cloud architecture should minimize always-on services and operational overhead.
- Prefer managed services where they reduce maintenance burden without lock-in to a single non-portable pattern.

### NFR-7 Data Governance

- Raw artifacts and generated outputs have a configurable retention period (MVP default: 24 months unless policy/legal requirements differ).
- User data export is supported for profile/preferences and notification history.
- Summary provenance records are immutable append-only once published.

## 8) Success Metrics (Pilot + Hardening)

1. **Activation:** % of signups completing city selection.
2. **Coverage:** # of meetings processed per supported city per month.
3. **Delivery:** notification send success rate.
4. **Engagement:** notification click-through/open-to-view rate.
5. **Retention:** % of users active again within 30 days.
6. **Quality floor (ECR):** Evidence Coverage Rate = % of key claims in a summary with at least one valid evidence citation/snippet.
7. **Phase 1.5 quality gate:** weekly audited sample must show ECR >= 85%; claims without adequate evidence must be labeled limited-confidence.

## 9) Launch Phasing

### Phase 1 (Pilot)

**MVP-Core objective:** deliver a reliable first end-to-end slice for one city with minimum operational complexity.

- 1 city
- architecture, schemas, and pipelines remain city-agnostic and ready for many configured cities
- automated scheduled ingestion for pilot city
- push notifications
- basic meeting summaries
- local-first setup validated end-to-end
- baseline reliability controls in production path (deterministic dedupe key, bounded retries, basic failure logging)
- baseline quality controls in production path (evidence pointers + limited-confidence labeling when evidence is weak)
- baseline source operations (last-success visibility + basic manual-review path for low-confidence runs)

### Phase 1.5 (Hardening)

**Hardening objective:** raise reliability, observability, and quality operations from baseline to sustained operational cadence.

- notification reliability hardening (retry/backoff tuning, dead-letter handling, replay tooling)
- observability hardening (dashboards, alert thresholds, failure triage)
- quality operations hardening (regular ECR audits, confidence calibration, reviewer workflow)
- source health and parser drift monitoring at operational cadence

### Phase 2

- multi-city rollout (operational expansion beyond pilot)
- improved extraction/summarization quality
- better user preferences
- AWS deployment hardening (monitoring, autoscaling, backups)

### Phase 3

- additional channels (email, SMS)
- richer personalization and trend tracking

## 10) Product Decisions (Locked for MVP)

1. **Auth provider:** AWS Cognito via Amplify Auth.
   - Rationale: aligns with existing Amplify hosting and avoids custom auth implementation.
2. **City model:** predefined city list only.
3. **Pilot launch strategy:**
   - Launch with one pilot city active by default (Primary: Eagle Mountain, UT)
   - Keep additional city configurations ready for expansion after pilot validation (Secondary candidate: Saratoga Springs, UT)
4. **Ingestion operation:** automated scheduled scraping/ingestion (not manual-only).
5. **Notification cadence:** immediate after meeting analysis completes.
6. **Push architecture:** PWA web push for MVP; native app push is post-MVP.
7. **Q&A in MVP:** deferred to post-MVP.
8. **AWS backend runtime:** container-first (App Runner for MVP, ECS/Fargate if scaling/advanced networking is needed).
9. **Primary data stores:** Postgres + object storage + vector retrieval layer.
   - MVP recommendation: Postgres (+ pgvector) and S3-compatible object storage.
10. **LLM hosting model:** managed model endpoint is the default for MVP; self-hosted OSS is a post-MVP optimization path.
11. **Additional auth providers:** Google only for MVP.

### 10.1 Tradeoff Notes (for chosen decisions)

#### Auth Provider: Cognito/Amplify vs Auth0/Clerk

- **Cognito/Amplify pros:** native AWS integration, no extra vendor bill, good fit with Amplify-hosted frontend.
- **Cognito/Amplify cons:** developer experience can be less polished than Auth0/Clerk in some flows.
- **Auth0/Clerk pros:** faster UX polish and easier auth customization.
- **Auth0/Clerk cons:** additional vendor dependency and cost.

#### Push: PWA Web Push vs Native Push

- **PWA web push pros:** fastest path with one codebase, good fit for MVP.
- **PWA web push cons:** browser/platform permission and delivery behavior can vary.
- **Native push pros:** best reliability/control and mobile UX.
- **Native push cons:** more engineering effort and app-store overhead.

#### Backend Runtime: Lambda vs Containers

- **Lambda/API Gateway pros:** low ops for bursty stateless APIs, pay-per-use.
- **Lambda/API Gateway cons:** less ideal for heavier long-running jobs and containerized ML workflows.
- **App Runner/ECS pros:** simpler fit for Python workers, scraping, and model-serving style workloads.
- **App Runner/ECS cons:** some always-on baseline cost and container ops.

#### Data Stores: Options and Tradeoffs

- **Postgres + pgvector:** strong default for MVP, fewer moving parts, works locally and in AWS.
- **Dedicated vector DB/OpenSearch:** may scale retrieval features better later, but adds cost and operational complexity.
- **Object storage (S3):** best for raw artifacts and source files; keep metadata/indexes in Postgres.
- **Local parity:** same pattern works locally using Postgres + local filesystem (or MinIO-compatible storage).

#### LLM Hosting: Managed Endpoint (MVP) vs Self-hosted OSS

- **Managed endpoint (MVP) pros:** fastest path to reliability, lower operational burden, simpler observability for early launch.
- **Managed endpoint (MVP) cons:** vendor cost/lock-in and less control over serving stack.
- **Self-hosted OSS pros:** model control and potential lower unit cost at steady volume.
- **Self-hosted OSS cons:** GPU provisioning, model ops, observability, and uptime burden.
- **Decision note:** revisit self-hosting after MVP when usage, latency, and cost baselines are measured.

## 11) Deployment Strategy (Local + AWS)

### 11.1 Local Development (required)

1. Run frontend, backend API, ingestion pipeline, and storage locally.
2. Local mode should support the full user journey: signup, city selection, meeting processing, push flow (or test equivalent), and reading summaries.
3. Local defaults should prioritize low setup complexity.
4. Local auth must work with localhost redirect/callback URLs and separate development OAuth app credentials.

### 11.2 AWS Deployment (required)

1. **Frontend:** AWS Amplify hosting is the preferred default path.
2. **Backend/API:** Deploy as containerized service behind HTTPS (App Runner default for MVP; ECS/Fargate as scale path).
3. **Storage:** Use object storage for source artifacts and durable DB for app data.
4. **Async processing:** Ingestion/summarization jobs run off request path via queue/worker pattern.
5. **Config/secrets:** Use AWS-native secret/config management in cloud; local .env for dev.

### 11.3 Architecture Principle

- Design around clear interfaces (ingestion, summarization, retrieval, notifications) so infrastructure can evolve without rewriting product logic.

## 12) Service Boundaries (Conceptual)

### 12.1 ETL / Ingestion Pipeline

- Fetches meeting materials by city from configured sources.
- Normalizes and stores source artifacts + extracted text/structure.
- Publishes processing-ready meeting records.

### 12.2 Summarization & Relevance Service

- Produces meeting summaries, key decisions, notable topics, and evidence links.
- Runs independently from UI request/response path.
- Exposes outputs consumable by both web views and notifications.

### 12.3 Web App

- Handles auth, user profile (including home city), meeting browsing, and preferences.
- Displays already-processed outputs and evidence.
- Triggers notifications based on user-city subscriptions and new processed meetings.

### 12.4 Chat/Q&A Service

- Deferred to post-MVP; can be enabled as a separate capability later.
- Uses retrieval over processed and/or source content with grounded citations.
- Should be loosely coupled so it can be added later without reworking core ETL + summaries.

## 13) Acceptance Criteria for MVP Exit

MVP is complete when all are true:

1. New user can sign in with managed auth (Google at minimum) and set home city.
2. At least one pilot city has recurring meeting ingestion and successful processing.
3. Processed meetings are visible in app with readable summaries and evidence pointers.
4. Subscribed users receive one correct push notification per new meeting in their city.
5. Unsubscribe/pause works and is respected.
6. Basic operational dashboard/logs exist for ingestion + notification health.
7. Notification reliability baseline is validated for MVP (deterministic dedupe key + bounded retry/backoff policy in operation); dead-letter/replay tooling is Phase 1.5.
8. Summary baseline quality controls are in place for MVP (evidence pointers for key claims where possible, and low-evidence claims are labeled limited-confidence); regular audited ECR operations (>= 85% weekly sample gate) are Phase 1.5.
9. Source health visibility and manual-review workflow are operational for pilot cities at a basic level; parser drift monitoring and advanced operational tooling are Phase 1.5.
