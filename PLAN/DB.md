# CouncilSense — Database Plan

## 1) Objectives and non-negotiables

- Ship MVP fast for one pilot city, without schema rewrites for multi-city expansion.
- Keep one canonical transactional store: PostgreSQL 16+.
- Enforce in DB (not just app code):
  - notification idempotency
  - evidence/provenance integrity
  - one current published summary per meeting
- Keep local-first parity with AWS: same schema/migrations in both environments.
- Store large files in object storage; DB stores metadata, checksums, pointers, provenance.

---

## 2) Decision notes (conflict resolution)

### Decision A — Status modeling (`ENUM` vs `CHECK`)
- **Conflict:** DB-1 prefers PostgreSQL enums; DB-3 prefers constrained text for easier migrations.
- **Decision:** Use `TEXT + CHECK` for status/label fields.
- **Why:** Faster forward-only schema evolution during MVP/hardening; avoids enum migration friction.

### Decision B — Schema layout (`core/ops/governance` vs flat public)
- **Conflict:** DB-1 uses separated schemas; DB-2/DB-3 are mostly flat.
- **Decision:** Use 3 schemas: `core`, `ops`, `governance`.
- **Why:** Clear ownership boundaries without extra infrastructure; supports least-privilege DB roles later.

### Decision C — Publication model
- **Conflict:** DB-2 uses `meeting_publications`; DB-1/DB-3 use `summary_versions`.
- **Decision:** Standardize on `core.summary_versions` with append-only versioning and `is_current`.
- **Why:** Clear lineage and simpler joins while preserving full history.

### Decision D — Notification idempotency key
- **Conflict:** unique composite (`user_id, meeting_id, type`) vs hash-based `dedupe_key`.
- **Decision:** Store both; enforce uniqueness on `dedupe_key` only, generated from deterministic input.
- **Why:** Stable portable idempotency contract across workers/services; explicit traceability in logs.

### Decision E — Quality operations depth in MVP
- **Conflict:** DB-2 includes rich drift/audit tables; DB-3 is leaner.
- **Decision:** Include minimal-but-concrete quality/drift tables in MVP (append-only), defer heavy analytics views to Phase 1.5.
- **Why:** Meets requirements for evidence quality and source/parser reproducibility without overbuilding.

### Decision F — `pgvector` timing
- **Conflict:** DB-1 includes now; DB-3 defers.
- **Decision:** Keep `pgvector` optional feature flag migration (`000X_pgvector_optional`), not required for MVP launch.
- **Why:** Reduces MVP risk while preserving retrieval path.

---

## 3) Canonical data architecture

- **Primary DB:** Postgres (`core`, `ops`, `governance`)
- **Object storage:** S3/MinIO for artifacts (raw PDFs, text extracts, normalized JSON)
- **Async runtime:** queue/scheduler outside DB (SQS/EventBridge or local adapter)
- **DB role:** source of truth for state, provenance, idempotency, and operational audit

---

## 4) Schema plan (implementation-ready)

## 4.1 `core` schema

### `core.cities`
- `id uuid pk`, `slug text unique`, `name`, `state_code`, `timezone`
- `enabled bool`, `priority_tier smallint check (1..100)`
- `created_at`, `updated_at`

Indexes:
- `unique(slug)`
- `(enabled, priority_tier)`

### `core.users`
- `id uuid pk`, `auth_subject text unique`, `email citext unique`
- `email_verified bool default false`
- `deleted_at`, `created_at`, `updated_at`

### `core.user_profiles`
- `user_id uuid pk fk -> users(id) on delete cascade`
- `home_city_id uuid fk -> cities(id)`
- `notifications_enabled bool default true`
- `notifications_paused_until timestamptz null`
- `created_at`, `updated_at`

Indexes:
- `(home_city_id)`
- `(home_city_id, notifications_enabled)`

### `core.push_subscriptions`
- `id uuid pk`, `user_id fk -> users(id) on delete cascade`
- `endpoint_hash text`, `endpoint_ciphertext text`
- `p256dh_key text`, `auth_key text`
- `status text check in ('active','invalid','expired','suppressed')`
- `failure_count int default 0 check (failure_count >= 0)`
- `last_success_at`, `last_failure_at`, `created_at`, `updated_at`

Indexes/constraints:
- `unique(user_id, endpoint_hash)`
- `(user_id, status)` partial on active recommended

### `core.city_sources`
- `id uuid pk`, `city_id fk -> cities(id) on delete cascade`
- `source_type text check in ('agenda','minutes','transcript','packet','feed','other')`
- `source_url text`, `enabled bool`
- `parser_name text`, `parser_version text`
- `health_status text check in ('healthy','degraded','failing','unknown')`
- `last_success_at`, `last_attempt_at`, `failure_streak int default 0`
- `created_at`, `updated_at`

Constraints/indexes:
- `unique(city_id, source_type, source_url)`
- `(city_id, enabled)`, `(health_status, last_success_at)`

### `core.meetings`
- `id uuid pk`, `city_id fk -> cities(id)`
- `meeting_uid text` (deterministic city-scoped key)
- `title text`, `meeting_date date`, `meeting_ts timestamptz null`
- `status text check in ('pending','processed','limited_confidence','failed','archived')`
- `latest_summary_version_id uuid null`
- `first_seen_at`, `published_at`, `created_at`, `updated_at`

Constraints/indexes:
- `unique(city_id, meeting_uid)`
- `(city_id, meeting_date desc, id)`
- `(city_id, status, meeting_date desc)`

### `core.artifacts`
- `id uuid pk`, `meeting_id fk -> meetings(id) on delete cascade`
- `city_source_id fk -> city_sources(id) null`
- `artifact_type text check in ('raw_pdf','raw_html','raw_text','minutes','packet','transcript','normalized_text','structured_json')`
- `storage_uri text`, `sha256 text`, `mime_type text`, `byte_size bigint`
- `source_section_ref text null`
- `retention_delete_after timestamptz null`
- `created_at`

Constraints/indexes:
- `unique(meeting_id, artifact_type, sha256)`
- `(meeting_id, artifact_type)`
- partial `(retention_delete_after)` where not null

### `core.processing_runs` (append-only)
- `id uuid pk`, `meeting_id fk -> meetings(id) on delete cascade`
- `city_id fk -> cities(id)`, `city_source_id fk -> city_sources(id) null`
- `trigger_type text check in ('scheduled','manual_rerun','repair')`
- `run_status text check in ('running','succeeded','failed','cancelled','manual_review_needed')`
- `parser_name`, `parser_version`, `extractor_version`, `summarizer_version`
- `extraction_confidence numeric(5,4) check between 0 and 1`
- `claim_count int default 0`, `claims_with_evidence_count int default 0`
- `ecr numeric(5,4)` (stored by app)
- `quality_gate_result text check in ('pass','limited_confidence','reject')`
- `started_at`, `finished_at`, `created_at`
- `failure_stage`, `failure_code`, `failure_message`

Indexes:
- `(meeting_id, started_at desc)`
- `(city_id, run_status, started_at desc)`
- `(quality_gate_result, started_at desc)`

### `core.summary_versions` (append-only after publish)
- `id uuid pk`, `meeting_id fk -> meetings(id) on delete cascade`
- `processing_run_id fk -> processing_runs(id)`
- `version_no int check (version_no > 0)`
- `is_current bool default false`
- `publication_status text check in ('processed','limited_confidence','retracted')`
- `confidence_label text check in ('high','medium','low','limited_confidence')`
- `short_summary text`
- `key_decisions jsonb default '[]'`
- `notable_topics jsonb default '[]'`
- `claim_count int default 0`
- `claims_with_evidence_count int default 0`
- `ecr numeric(5,4)`
- `published_at timestamptz null`
- `created_at`

Constraints/indexes:
- `unique(meeting_id, version_no)`
- `unique(meeting_id) where is_current = true`
- `(meeting_id, published_at desc)`
- check: `claims_with_evidence_count <= claim_count`

### `core.claims`
- `id uuid pk`, `summary_version_id fk -> summary_versions(id) on delete cascade`
- `claim_order int`, `claim_text text`
- `confidence_score numeric(5,4) null`
- `limited_confidence bool default false`
- `created_at`

Constraints/indexes:
- `unique(summary_version_id, claim_order)`
- `(summary_version_id, claim_order)`

### `core.claim_evidence`
- `id uuid pk`, `claim_id fk -> claims(id) on delete cascade`
- `artifact_id fk -> artifacts(id)`
- `section_ref text null`
- `char_start int null`, `char_end int null`
- `excerpt text not null`
- `created_at`

Constraints/indexes:
- check offsets: both null or `char_start >= 0 and char_end > char_start`
- `(claim_id)`, `(artifact_id)`

### `core.notification_outbox`
- `id uuid pk`
- `user_id uuid fk -> users(id)` (user row anonymized, not deleted, to preserve history)
- `meeting_id uuid fk -> meetings(id) on delete cascade`
- `city_id uuid fk -> cities(id)`
- `notification_type text check in ('meeting_published')`
- `dedupe_key text not null` (`sha256(user_id|meeting_id|notification_type)`)
- `payload jsonb not null`
- `status text check in ('queued','processing','sent','failed','suppressed','dead_lettered')`
- `attempt_count int default 0 check (attempt_count >= 0)`
- `max_attempts int default 6 check (max_attempts > 0)`
- `next_attempt_at timestamptz default now()`
- `last_attempt_at timestamptz null`
- `last_error_code text null`, `last_error_message text null`
- `sent_at timestamptz null`
- `created_at`, `updated_at`

Constraints/indexes:
- `unique(dedupe_key)` **(idempotency hard guarantee)**
- `(status, next_attempt_at)` for worker polling
- `(city_id, meeting_id)`, `(user_id, created_at desc)`

### `core.notification_attempts` (append-only)
- `id bigserial pk`, `outbox_id fk -> notification_outbox(id) on delete cascade`
- `attempt_no int`, `attempted_at timestamptz`
- `result text check in ('success','retryable_failure','permanent_failure','suppressed')`
- `provider_message_id`, `http_status`, `provider_error_code`, `provider_error_message`
- `backoff_seconds int`, `diagnostics jsonb default '{}'`

Constraints/indexes:
- `unique(outbox_id, attempt_no)`
- `(result, attempted_at desc)`, `(attempted_at desc)`

## 4.2 `ops` schema (append-only ops telemetry)

### `ops.source_health_snapshots`
- source checks (`fetch|parse|publish_lag`), status (`ok|warn|error`), metadata JSONB
- index `(source_id, checked_at desc)`, `(status, checked_at desc)`

### `ops.parser_versions`
- parser identity (`parser_name`, `parser_semver`, `git_sha`, `prompt_version`)
- unique on composite identity

### `ops.parser_drift_events`
- drift detection events with severity/metric baseline/current/threshold
- index `(city_id, detected_at desc)`, `(severity, detected_at desc)`

### `ops.dead_letter_notifications`
- `outbox_id unique fk`, reason, dead_lettered_at, replayed_at, replay_result

## 4.3 `governance` schema

### `governance.retention_policies`
- `entity_name unique`, `retention_days`, `legal_hold`, `updated_at`

### `governance.export_requests`
- export workflow state: `requested|running|completed|failed|expired`
- `artifact_uri`, `expires_at`, error fields

### `governance.deletion_requests`
- deletion/anonymization workflow: `requested|running|completed|failed`
- `requested_at`, `completed_at`, `notes`

---

## 5) Hard controls for evidence/provenance quality

1. **Append-only publication lineage**
   - Trigger: reject `UPDATE/DELETE` on `summary_versions`, `claims`, `claim_evidence` when `published_at is not null`.
2. **Single current version**
   - Partial unique index on `summary_versions(meeting_id) where is_current = true`.
3. **Quality gate persistence**
   - `processing_runs.quality_gate_result` required before publish transaction.
4. **ECR representation**
   - Store `claim_count`, `claims_with_evidence_count`, and `ecr` on `summary_versions`.
5. **Limited-confidence enforcement**
   - Publish as `publication_status='limited_confidence'` when gate fails; never publish as `processed` without gate pass.

---

## 6) Transaction boundaries (must be atomic)

### TX-1: Ingest upsert
- Upsert `meetings` by `(city_id, meeting_uid)`.
- Insert deduped `artifacts`.
- Insert `processing_runs` row (`running`).

### TX-2: Publish summary + provenance + state flip + notification enqueue
In one transaction:
1. Insert new `summary_versions(version_no = prev+1, is_current=true)`.
2. Insert `claims` and `claim_evidence`.
3. Set prior current version `is_current=false`.
4. Update `meetings.status`, `published_at`, `latest_summary_version_id`.
5. Insert `notification_outbox` rows for eligible users using `ON CONFLICT (dedupe_key) DO NOTHING`.

### TX-3: Worker claim/send
- Claim batch with `FOR UPDATE SKIP LOCKED` from `notification_outbox` where `status in ('queued','failed') and next_attempt_at <= now()`.
- Transition to `processing`, send push, append `notification_attempts`.
- Update outbox row to `sent`, `failed` (+ backoff), `suppressed`, or `dead_lettered`.

---

## 7) Migration strategy (Alembic, forward-only)

1. **Expand**
   - Create schemas/tables/indexes as additive.
   - Add nullable new columns and new tables first.
2. **Dual-write**
   - Writers persist old + new publication path for one release window (if legacy exists).
3. **Backfill**
   - Convert historical summaries into `summary_versions` v1 rows.
   - Backfill counters (`claim_count`, `claims_with_evidence_count`, `ecr`).
4. **Cutover**
   - Reader APIs switch to `summary_versions is_current=true`.
   - Enforce stricter constraints (`NOT NULL`, unique partial indexes).
5. **Contract**
   - Remove deprecated fields after parity validation.
6. **Operational rules**
   - `CREATE INDEX CONCURRENTLY` on large prod tables.
   - Idempotent backfills in chunks.
   - No edit-in-place of previously applied migrations.

---

## 8) Retention and governance policy

- Default retention: 24 months for artifacts and generated outputs (configurable).
- Keep publication provenance at least retention horizon; optional longer for audit.
- Notification attempts and source health snapshots retained 12+ months, then archived.
- Monthly archival job:
  - export old append-only partitions/slices to object storage (Parquet/CSV),
  - verify checksum + row counts,
  - then purge per policy.
- User deletion:
  - hard-delete profile + push subscriptions,
  - anonymize `users.email` and other PII,
  - preserve non-PII IDs for historical integrity.

---

## 9) API and data-access boundaries

Repository boundaries:
- `IdentityRepo`: users, profiles, subscriptions
- `CityRepo`: cities, city_sources
- `MeetingRepo`: meetings, artifacts, processing_runs
- `PublicationRepo`: summary_versions, claims, claim_evidence
- `NotificationRepo`: outbox, attempts, dead letters
- `GovernanceRepo`: retention/export/deletion workflows

Rules:
- Cross-domain writes only via service-layer transactions (never ad hoc multi-repo writes).
- Reader APIs are read-only against publication tables (`is_current=true`).
- Only worker services mutate outbox statuses/attempts.

---

## 10) Phased rollout

### Phase 1 (MVP pilot city)
- Implement full canonical schema above.
- Enable ingestion, publish pipeline, evidence capture, and outbox notifications.
- Enforce dedupe key uniqueness + retry/backoff + invalid subscription suppression.
- Ship basic ops views over `processing_runs`, `notification_attempts`, `source_health_snapshots`.

### Phase 1.5 (hardening)
- Add replay tooling and dead-letter operations.
- Add alert thresholds (stale sources, failure spikes, queue lag).
- Add ECR audit workflow (`quality_reviews` optional table/materialized views).
- Add partitioning for high-volume append-only tables as needed.

### Phase 2 (multi-city expansion)
- Enable cities via config/data only (no schema redesign).
- Tune indexes and worker concurrency from observed workload.
- Optional read replica and optional `pgvector` activation for semantic retrieval features.

---

## 11) Implementation checklist (first sprint)

1. Create migrations for `core`, `ops`, `governance` schemas and all tables/indexes.
2. Implement publish immutability triggers.
3. Implement TX-2 publish flow with outbox idempotent enqueue.
4. Implement worker `SKIP LOCKED` claim/send loop with attempt audit.
5. Seed pilot city + sources + retention defaults.
6. Add migration/constraint tests:
   - duplicate dedupe rejected,
   - one current summary enforced,
   - published provenance immutable,
   - invalid statuses rejected,
   - publish+enqueue atomic rollback behavior validated.
