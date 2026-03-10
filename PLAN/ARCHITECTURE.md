# CouncilSense — Architecture (Pragmatic MVP, Scalable Path)

**Date:** 2026-02-26  
**Status:** Baseline architecture (implementation-ready)

## 1) Architecture Goals

- Ship a reliable MVP for one pilot city while keeping all core models and flows city-agnostic.
- Keep operations simple in Phase 1 (few moving parts, managed services, clear runbooks).
- Preserve clean seams for Phase 2 multi-city scale without rewriting product logic.
- Enforce evidence-grounded summaries and deterministic notification idempotency from day one.
- Run the full product locally with the same contracts used in AWS.

## 2) Scope Guardrails

### In scope for MVP (Phase 1)

- Managed auth (Cognito) with Google login.
- Home city set/edit, notification pause/unpause.
- Scheduled city-driven ingestion (independent of user count).
- Summary + key decisions + notable topics + evidence snippets.
- PWA web push notifications.
- Baseline reliability, quality controls, and operational visibility.

### Explicitly deferred

- Multi-city following per user.
- Email/SMS channels.
- Q&A/chat experience.
- OCR-heavy ingestion and advanced admin portal.

## 3) Key Design Decisions

1. **Runtime shape:** Modular monolith backend (API + worker modules in one codebase) deployed as containers.
2. **Async model:** Queue-driven processing for ingestion, extraction, summarization, publication, notification.
3. **Data stack:** Postgres (+ pgvector) for app/processing/provenance data; S3-compatible storage for raw/generated artifacts.
4. **Notification policy:** Deterministic dedupe key `user_id + meeting_id + notification_type` enforced by unique constraint.
5. **Quality policy:** If evidence quality is insufficient, publish `limited_confidence` rather than strong synthesized claims.
6. **Meeting identity:** Deterministic city-scoped identity from canonical meeting attributes; source refs remain metadata.
7. **Operations model:** Baseline controls in Phase 1; DLQ/replay/alert hardening in Phase 1.5.
8. **Cloud runtime:** App Runner first, ECS/Fargate path only when scaling/network needs justify it.

## 4) Service Boundaries (Logical Modules)

Keep as modules in one backend service for Phase 1; split only when measured load requires.

1. **Identity & Profile**
   - User profile, home city, preferences, push subscription registration.
2. **City Registry**
   - Supported cities, source configs, city enablement, priority tiers, source health state.
3. **Ingestion**
   - Fetch and persist source artifacts; normalize metadata.
4. **Extraction**
   - Convert artifacts to structured meeting content with confidence scores.
5. **Summarization & Evidence**
   - Produce summary/decisions/topics/claims and attach evidence citations.
6. **Publication**
   - Apply quality gate; publish `processed` or `limited_confidence`.
7. **Notification**
   - Subscriber fan-out, dedupe, retries/backoff, invalid subscription suppression, delivery logging.
8. **Reader API**
   - City meeting list and meeting detail payloads for app consumption.

## 5) Deployment Topology

## 5.1 Local (required parity)

- Next.js frontend.
- Python API process + Python worker process.
- Local Postgres with pgvector.
- Local object storage adapter (filesystem or MinIO).
- Local queue adapter + scheduler (cron/CLI loop).
- Cognito dev config with localhost OAuth redirect URIs.
- Push default: test-equivalent delivery path; optional HTTPS tunnel for true browser push parity.

## 5.2 AWS (MVP default)

- **Frontend:** AWS Amplify Hosting.
- **Auth:** Cognito + Google federation.
- **Backend runtime:** App Runner containers (API and worker entrypoints).
- **Queue:** SQS.
- **Scheduler:** EventBridge schedules.
- **Database:** RDS Postgres (+ pgvector).
- **Object storage:** S3.
- **Secrets/config:** Secrets Manager + Parameter Store.
- **Observability:** CloudWatch logs/metrics/dashboards.

Principle: environment differences are configuration-driven only.

## 6) Data Model Domains

## 6.1 Identity & preferences

- `users` (auth subject, email, timestamps)
- `user_profiles` (home_city_id, notifications_enabled/paused)
- `push_subscriptions` (endpoint keys/status/refreshed_at)

## 6.2 City/source registry

- `cities` (enabled, priority_tier)
- `city_sources` (source URL/type, parser_version, health_status, last_success_at)

## 6.3 Meetings & artifacts

- `meetings` (city_id, date/title, deterministic identity, status)
- `artifacts` (raw/extracted URIs, checksum, metadata)
- `processing_runs` (status, timings, extraction_confidence, parser_version)

## 6.4 Summaries & provenance

- `summary_versions` (short summary, decisions, topics, confidence_label, published_at)
- `claims` (claim text, confidence, limited_confidence flag)
- `evidence` (artifact_id, section/offset, excerpt) — immutable once published

## 6.5 Notification delivery

- `notification_deliveries` (dedupe_key unique, attempt_count, status, last_attempt_at)

Governance defaults:

- Retention default 24 months (configurable).
- Provenance append-only post-publish.
- User export for profile/preferences/notification history.
- User deletion removes/anonymizes personal profile data within defined SLA.

## 7) Async Flows

## 7.1 Scheduled ingest-to-publish

1. Scheduler triggers runs for configured cities.
2. Ingestion jobs fetch and store artifacts.
3. Extraction jobs normalize meeting content and score confidence.
4. Summarization jobs generate summary/decisions/topics/claims.
5. Evidence resolver grounds claims with citation schema.
6. Publication applies quality gate and sets `processed` or `limited_confidence`.
7. Notification fan-out job enqueues per subscribed user in that city.

## 7.2 Notification send

1. Notification worker builds dedupe key.
2. Insert/send attempt is idempotent via unique dedupe constraint.
3. Retry with exponential backoff (bounded attempts).
4. Mark expired/invalid subscriptions as suppressed.
5. Persist attempt outcomes for ops visibility.

## 7.3 Failure isolation

- City/source failures remain scoped to those jobs.
- Failed jobs are retryable and do not block other city pipelines.
- Request-path APIs remain available during pipeline failures.

## 8) Reliability and Idempotency

### Phase 1 baseline

- Queue-based asynchronous execution.
- Deterministic notification dedupe key with DB uniqueness enforcement.
- Bounded retries with exponential backoff + jitter.
- Run statuses: `pending`, `processed`, `failed`, `limited_confidence`.
- Source health markers and last-success timestamps per source.

### Phase 1.5 hardening

- Dead-letter queues and replay tooling.
- Tuned retry policies by job type.
- Operational thresholds for failure rates and latency.
- Replay outcome tracking.

## 9) Quality and Evidence Controls

### Output contract

- Summary output includes:
  - short summary
  - key decisions/actions
  - notable topics
  - claim-level evidence pointers where possible

### Citation schema

- Required fields per evidence item:
  - source artifact id
  - section reference or offsets
  - excerpt snippet

### Confidence policy

- If minimum evidence quality is unmet, output is labeled `limited_confidence`.
- Claims without adequate grounding are not presented as certain.
- Low extraction confidence is flagged for manual review path.

### Quality operations

- Track Evidence Coverage Rate (ECR) continuously.
- Phase 1.5 quality gate: weekly audited sample with ECR target >= 85%.

## 10) Observability

### Metrics

- Ingestion success/failure by city/source.
- Processing durations and p95 ingest-to-publish latency.
- Notification enqueue/send success/failure and retry counts.
- Invalid subscription suppression counts.
- Quality signals: `limited_confidence` rate, extraction confidence distribution, ECR.

### Logs

- Processing run lifecycle (with run IDs, parser/source versions).
- Notification attempts (with dedupe key, attempt, outcome).
- Quality gate decisions and evidence coverage summaries.

### Dashboards/alerts

- Source freshness and last-success views.
- Pipeline throughput/failure heatmap by city/source.
- Notification health panel.
- Phase 1.5: alert thresholds for failures, latency regressions, DLQ growth.

## 11) Security and Privacy

- Managed auth only (Cognito + Google); no custom password handling.
- Authorization: users can modify only their own profile/preferences/subscriptions.
- Internal ingestion/admin endpoints are role-restricted.
- Data minimization: only required PII (email, city, notification prefs/subscriptions).
- Encryption in transit and at rest (managed AWS controls).
- Secrets via secret manager; no secrets in repo.
- Privacy policy, terms, retention policy, deletion workflow required before pilot launch.

## 12) Phased Delivery

## Phase 1 (Pilot MVP)

- One pilot city active by default.
- End-to-end scheduled ingestion and publishing.
- Reader pages with summary/decisions/topics/evidence.
- Push notifications with idempotent dedupe and bounded retries.
- Baseline ops visibility and baseline quality controls.

**Exit criteria**

- Google sign-in + home city onboarding/edit works.
- Recurring pilot processing works.
- Users receive one correct push per meeting/type.
- Pause/unsubscribe respected.
- Basic ingestion/notification health visible.
- Limited-confidence policy active in production path.

## Phase 1.5 (Hardening)

- DLQ + replay tooling.
- Alert thresholds and triage runbooks.
- ECR audit cadence and confidence calibration.
- Source/parser drift monitoring improvements.

## Phase 2 (Expansion)

- Multi-city operational rollout via configuration and source adapters.
- Quality and extraction improvements at scale.
- AWS scaling hardening (worker pool split, autoscaling, backup/restore maturity).
- Optional service decomposition only where justified by measured bottlenecks.

## 13) Implementation Slices (Engineering Plan)

1. **Slice A: Identity/Profile/Reader foundation**
   - Auth integration, profile APIs/UI, city validation, meetings list/detail read endpoints.
2. **Slice B: Pipeline baseline**
   - Scheduler, queue contracts, ingestion/extraction/summarization/provenance persistence.
3. **Slice C: Notification baseline**
   - Push subscription handling, fan-out, dedupe uniqueness, retries/backoff, delivery logs.
4. **Slice D: Ops + quality baseline**
   - Dashboards/log schema, source health views, limited-confidence handling, runbooks.
5. **Slice E (Phase 1.5): Hardening**
   - DLQ/replay, alerts, ECR audit workflow, parser drift monitoring.

## 14) Requirement Traceability (Condensed)

- **FR-1/FR-2:** Managed auth + profile/home city + preference controls.
- **FR-3:** Scheduled city-driven queue pipeline with status tracking and retryability.
- **FR-4:** Claim/evidence schema + uncertainty labeling (`limited_confidence`).
- **FR-5:** Subscriber fan-out + deterministic dedupe + retry/backoff + delivery logs/suppression.
- **FR-6:** User-scoped authorization and restricted internal ops endpoints.
- **FR-7:** Source health tracking, parser version capture, low-confidence review path, failure isolation.
- **NFR-1..NFR-7:** Reliability controls, latency targets, security/privacy, observability, local/cloud parity, cost simplicity, governance/retention/export/immutability.
