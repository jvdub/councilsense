# CouncilSense — Backend Plan

## 1) Scope and goals

This plan merges the strongest elements of the three backend proposals into one implementation-ready MVP path that is reliable for one pilot city and structurally ready for multi-city scale.

**MVP outcomes**
- Managed auth (Cognito + Google), user profile/home city, notification preferences.
- City-driven scheduled ingestion (not user-count-driven).
- Evidence-grounded meeting outputs: summary, key decisions/actions, notable topics.
- Deterministic, idempotent push notifications.
- Local-first parity with AWS using shared contracts and config-driven environment differences.

**Explicitly deferred**
- Multi-city follow per user, Q&A/chat runtime, SMS/email channels, public API.

---

## 2) Architecture decision notes (conflicts resolved)

1. **Runtime shape**
   - Decision: modular monolith with two processes (`api`, `worker`) in one codebase.
   - Why: fastest MVP delivery and debugging, with clean seams for later decomposition.

2. **Data model publication shape**
   - Decision: `summary_versions` append-only model with exactly one `is_current=true` per meeting.
   - Why: stronger lineage and safer roll-forward than mutable single-row summaries.

3. **Idempotency key strategy**
   - Decision: canonical `dedupe_key = sha256(user_id|meeting_id|notification_type)` with DB unique constraint; also store component fields for audit/query.
   - Why: deterministic cross-service contract and hard duplicate prevention.

4. **Status fields**
   - Decision: `TEXT + CHECK` constraints (not Postgres enums) for evolving statuses.
   - Why: lower migration friction during MVP/hardening.

5. **Schema organization**
   - Decision: three DB schemas: `core`, `ops`, `governance`.
   - Why: clear ownership boundaries now, easier least-privilege and growth later.

6. **Vector capability**
   - Decision: keep `pgvector` optional/flagged migration, not launch-critical.
   - Why: protects MVP timeline while preserving future retrieval path.

7. **Quality operations depth**
   - Decision: enforce baseline quality gate in MVP; richer audit/alert workflows in Phase 1.5.
   - Why: correctness now, operational depth iteratively.

---

## 3) Backend package structure (implementation target)

```text
backend/
  pyproject.toml
  alembic.ini
  migrations/
  src/councilsense/
    app/
      main.py                  # API entrypoint
      worker.py                # worker entrypoint
      settings.py
      logging.py
    api/
      routes/
        system.py              # /healthz /readyz /metrics
        me.py                  # profile + preferences
        subscriptions.py       # push subscriptions
        meetings.py            # reader endpoints
        internal_ops.py        # role-restricted rerun/scan
      dependencies.py
      schemas/
    application/
      services/                # use-case orchestration
      policies/                # retry, quality thresholds, authz policies
      orchestrators/           # ingest/publish/notify flows
    domain/
      identity/
      city_registry/
      meetings/
      ingestion/
      extraction/
      summarization/
      publication/
      notifications/
      quality/
      governance/
    contracts/
      events.py                # job payload schemas + versions
      statuses.py
      ids.py
      quality.py
    infra/
      db/
        models/
        repositories/
        unit_of_work.py
      queue/
        sqs_adapter.py
        local_adapter.py
      storage/
        s3_adapter.py
        local_fs_adapter.py
      push/
        webpush_adapter.py
      llm/
        managed_provider.py
      source_clients/
      metrics/
      tracing/
    workers/
      scheduler/
      consumers/
      tasks/
  tests/
    unit/
    integration/
    contract/
    resilience/
    e2e/
```

**Boundary rules**
- `domain` contains invariants and cannot import infra SDK adapters.
- Cross-domain writes only via `application.services` + `unit_of_work`.
- API and worker layers are thin entrypoints over services.

---

## 4) API surface (`/v1`)

## 4.1 System
- `GET /healthz` (liveness)
- `GET /readyz` (DB/queue readiness)
- `GET /metrics` (restricted in cloud)

## 4.2 User/profile
- `GET /me`
- `PATCH /me` (home city, notifications enabled, pause-until)
- `DELETE /me` (starts async anonymize/delete workflow)

## 4.3 Push subscriptions
- `POST /me/push-subscriptions`
- `GET /me/push-subscriptions`
- `DELETE /me/push-subscriptions/{subscription_id}`

## 4.4 Reader
- `GET /cities/{city_id}/meetings?cursor=&limit=&status=`
- `GET /meetings/{meeting_id}`
- `GET /meetings/{meeting_id}/evidence`

## 4.5 Internal ops (role-restricted)
- `POST /internal/cities/{city_id}/scan`
- `POST /internal/meetings/{meeting_id}/rerun`
- `GET /internal/runs/{processing_run_id}`
- `POST /internal/notifications/replay/{outbox_id}` (full replay tooling in Phase 1.5)

---

## 5) Job contracts (versioned event schema)

All jobs include envelope:
- `job_id`, `event_type`, `event_version`, `idempotency_key`, `trace_id`, `created_at`, `attempt`, `source`.

## 5.1 `city.scan.requested`
Purpose: discover candidate meetings for one city and window.

## 5.2 `meeting.ingest.requested`
Purpose: fetch/source artifacts and upsert canonical meeting/artifact metadata.

## 5.3 `meeting.extract.requested`
Purpose: normalize artifacts into structured sections with extraction confidence.

## 5.4 `meeting.summarize.requested`
Purpose: generate summary, decisions, topics, claims.

## 5.5 `meeting.publish.requested`
Purpose: run quality gate and atomically publish summary/provenance + enqueue notifications.

## 5.6 `notification.enqueue.requested`
Purpose: fan-out to subscriber outbox rows with deterministic dedupe key.

## 5.7 `notification.send.requested`
Purpose: claim outbox items, send push, persist attempt result, transition state.

**Versioning rule**
- Additive payload fields: minor version.
- Breaking payload changes: new event version + consumer dual-read during rollout.

---

## 6) Reliability and idempotency contracts

## 6.1 Invariants (enforced in DB)
- Unique meeting identity: `(city_id, meeting_uid)`.
- Unique notification dedupe: `unique(dedupe_key)`.
- Exactly one current summary per meeting: partial unique index on `is_current=true`.
- Published provenance append-only (`summary_versions`, `claims`, `claim_evidence`, `notification_attempts`).

## 6.2 Transaction boundaries
- **TX-A Ingest:** upsert meeting + deduped artifacts + create `processing_run`.
- **TX-B Publish (atomic):** insert summary version + claims/evidence + flip current + update meeting status + outbox enqueue.
- **TX-C Notify send:** claim row (`FOR UPDATE SKIP LOCKED`) + send + append attempt + state transition.

## 6.3 Retry/backoff
- Exponential backoff + jitter, bounded attempts per job type.
- Retry only transient errors; permanent errors transition directly to terminal states (`suppressed`/`failed`).
- Exhausted retries go to DLQ pathway (baseline visibility MVP; replay tooling Phase 1.5).

## 6.4 Failure isolation
- Per-city and per-meeting isolation; failures do not block other cities/meetings.
- Reader APIs remain available during worker degradation.

---

## 7) Quality gate and publication policy

## 7.1 Required publish artifacts
- `short_summary`
- `key_decisions[]`
- `notable_topics[]`
- `claims[]` with evidence pointers where available.

## 7.2 Evidence schema
Each evidence item includes:
- `artifact_id`
- `section_ref` and/or offsets
- `excerpt`

## 7.3 Gate outcomes
- `pass` → publish as `processed`.
- `limited_confidence` → publish with explicit low-confidence label.
- `reject` → no publish; run remains failed/manual-review-needed.

## 7.4 MVP thresholds (configurable)
- Citation schema validity required.
- Evidence Coverage Rate tracked each run.
- MVP publish floor permissive enough for pilot reliability; hardening adds strict weekly audited gate (target ECR >= 85%).

---

## 8) Observability and operations

## 8.1 Logs (structured)
Include at minimum:
- `request_id`, `trace_id`, `job_id`, `city_id`, `meeting_id`, `processing_run_id`, `dedupe_key`, `event`, `duration_ms`, outcome fields.

## 8.2 Metrics
- Ingestion success/failure by city/source.
- Ingest-to-publish latency p95.
- Notification enqueue/send success/failure/retry counts.
- Queue lag and DLQ volume.
- Source freshness (`last_success_age`).
- `limited_confidence` rate and ECR distribution.

## 8.3 Dashboards/runbooks
MVP:
- pipeline health, source freshness, notification health.
Phase 1.5:
- alert thresholds, DLQ replay workflow, parser/source drift response, low-ECR incident playbook.

---

## 9) Security and privacy baseline

- Managed auth only (Cognito + Google federation), JWT validation against JWKs.
- User-scoped authorization for profile/preferences/subscriptions.
- Internal ops endpoints restricted by service role claims.
- Secrets only via Secrets Manager/SSM in cloud; local `.env` for dev.
- Encryption in transit and at rest; no secrets in repo/logs.
- Data minimization: email, city, preferences, push subscription data only.
- Governance workflows: retention (default 24 months), export request, deletion/anonymization SLA.

---

## 10) Local and cloud deployment

## 10.1 Local (required parity)
- Processes: `web`, `api`, `worker`, `scheduler`.
- Data/services: Postgres, local storage adapter (filesystem/MinIO), local queue adapter.
- Auth: Cognito dev app with localhost callbacks.
- Push: test adapter default; optional HTTPS tunnel for real web push parity.

## 10.2 AWS MVP
- Frontend: Amplify Hosting.
- Auth: Cognito + Google.
- API/worker: App Runner containers.
- Queue: SQS.
- Scheduler: EventBridge.
- DB: RDS Postgres.
- Object storage: S3.
- Config/secrets: SSM + Secrets Manager.
- Observability: CloudWatch (+ OTel instrumentation).

## 10.3 Scale path
- Move worker/API to ECS/Fargate when queue lag, throughput, or networking/compliance needs exceed App Runner simplicity.
- Enable additional cities by configuration/data, not schema redesign.

---

## 11) Phased implementation plan

## Phase 0 — Foundation (week 1)
- Scaffold package structure, settings, logging/tracing, DB session, migrations baseline, auth middleware.
- Seed pilot city and source configs.
- CI gates: lint/type/unit smoke.

## Phase 1 — Core pipeline + reader (weeks 2–4)
- Implement scan→ingest→extract→summarize→publish orchestration.
- Implement quality gate + limited-confidence path.
- Deliver meetings list/detail/evidence reader endpoints.

## Phase 2 — Notifications + preferences (weeks 4–6)
- Push subscription APIs.
- Outbox fan-out and send worker with bounded retry/backoff and suppression.
- Profile preference controls fully wired to delivery behavior.

## Phase 3 — Operational hardening (Phase 1.5, weeks 6–8)
- DLQ handling and replay tooling.
- Alert thresholds and runbooks.
- ECR weekly audit workflow and confidence calibration.

## Phase 4 — Multi-city expansion (post-pilot)
- Enable additional cities via config.
- Tune concurrency/indexes from observed load.
- Optional `pgvector` activation for retrieval roadmap features.

---

## 12) Definition of done (MVP backend)

MVP backend is complete when:
1. User can sign in, set/edit home city, and manage notification preferences.
2. Scheduled city-driven pipeline processes pilot meetings end-to-end.
3. Meeting detail returns summary, decisions, topics, and evidence pointers.
4. Notification delivery is idempotent (one logical send per user/meeting/type).
5. Pause/unsubscribe/suppression behavior is enforced.
6. Operational dashboards show ingestion and notification health.
7. Limited-confidence publication policy is active in production path.