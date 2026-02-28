# ST-012 Parity Architecture Contract (Local-First + AWS Portable Runtime)

## Purpose

Define behavior-level parity between local and AWS runtime shapes so one codebase and one set of contracts execute in both environments.

Scope for this contract is limited to foundational mapping and runtime behavior guarantees required by ST-012 task chain.

## Service Mapping (Local -> AWS)

| Concern | Local runtime | AWS runtime | Parity contract |
| --- | --- | --- | --- |
| Web | Next.js local dev server | Amplify Hosting | Same frontend artifact and API contract; environment sets backend base URL only. |
| API | Python API process | App Runner service (API entrypoint) | Same API handlers, auth middleware, request/response schema, and auth-session behavior. |
| Worker | Python worker process | App Runner service (worker entrypoint) | Same worker logic for notification outbox handling, retry classification, and delivery status transitions. |
| Database | Postgres (+ pgvector where enabled) | RDS Postgres (+ pgvector where enabled) | Same schema and migration history; dedupe uniqueness and status transitions enforced identically at DB layer. |
| Storage | Filesystem adapter or MinIO-compatible object storage | S3 | Artifact interface contract is stable: key + metadata + immutable evidence pointers post publish. |
| Queue | Local queue adapter (in-memory/polling loop) | SQS | Queue payload contract, idempotent consumption rules, and retry semantics are stable across adapters. |
| Scheduler | Local cron/CLI loop | EventBridge schedule | Scheduler emits identical city-scan enqueue intent; only trigger mechanism differs. |
| Auth | Cognito dev app (localhost callbacks) | Cognito + Google federation | Token/session validation contract and profile authorization checks remain identical. |
| Secrets/config | `.env` and local process env | Secrets Manager + Parameter Store + service env | Same setting names and parsing rules; source of values differs only by environment. |
| Observability | Structured logs + local metric sink | CloudWatch logs/metrics/dashboards | Same event names, required keys, stage/outcome labels, and metric names. |

## Behavior Parity Contract

### 1) Idempotency

- Notification dedupe key remains deterministic from `(user_id, meeting_id, notification_type)` and versioned.
- Outbox enqueue uses conflict-safe insert semantics and treats conflicts as duplicate/no-op outcomes.
- Delivery terminal states (`sent`, `suppressed`, `invalid_subscription`, `expired_subscription`) are final for a dedupe tuple.
- No environment may weaken dedupe uniqueness guarantees.

### 2) Retry semantics

- Retryable failures are bounded by configured retry/backoff policy; non-retryable failures transition directly to terminal/non-retry path.
- Retry outcome labeling (`retry`, `failure`, `invalid_subscription`, `expired_subscription`, `success`) is identical across environments.
- Backoff schedule values may be configured per environment, but monotonic bounded retry policy is mandatory in both.

### 3) Message visibility behavior

- A message is considered visible for handling only when eligible by queue/outbox readiness state.
- Local adapter and SQS must both preserve at-least-once delivery assumptions.
- Worker processing must be idempotent so duplicate deliveries caused by visibility timeout/lease expiry do not produce duplicate logical sends.
- Competing consumers must not violate dedupe or terminal-state rules.

## Acceptable Differences and Compensating Controls

| Difference | Allowed? | Compensating control |
| --- | --- | --- |
| Queue transport implementation differs (local adapter vs SQS) | Yes | Enforce payload schema validation, idempotent worker behavior, and parity smoke checks for duplicate handling. |
| Object storage backend differs (filesystem/MinIO vs S3) | Yes | Enforce immutable post-publish evidence references and stable artifact key contract. |
| Scheduler trigger mechanism differs (loop/cron vs EventBridge) | Yes | Enforce same enqueue intent contract (`city_id`, `cycle_id`, `run_id`) and deterministic run identity generation. |
| Secrets source differs (.env vs secret managers) | Yes | Enforce startup validation on required values and fail fast on invalid configuration. |
| Observability sink differs (local sink vs CloudWatch) | Yes | Enforce canonical structured fields and metric names/labels from ST-011 contract. |

## Startup Dependency Matrix

| Runtime unit | Hard dependencies | Degraded/optional dependencies | Startup contract |
| --- | --- | --- | --- |
| Web | API base URL, auth config, VAPID public key (if push enabled) | Push capability in browser | Fail fast on missing required env; render app with capability-based push UX fallback. |
| API | Postgres connectivity, auth session secret, city registry seed access | Object storage (for non-request path operations) | Fail startup when DB/auth settings invalid; expose health endpoints only when core deps ready. |
| Worker | Postgres connectivity, queue/outbox readiness, notification contract parser | Push provider/transient network | Fail startup on invalid retry/idempotency config; continue loop with bounded retries for transient delivery failures. |
| Scheduler | City registry access, queue producer | None | Skip disabled cities; enqueue only enabled city scans using deterministic cycle/run IDs. |

## Required Configuration Knobs Per Environment

Current implemented baseline knobs:

| Setting | Local | AWS | Contract |
| --- | --- | --- | --- |
| `AUTH_SESSION_SECRET` | Required (dev default permitted only for local) | Required from secret manager/env | Must be non-empty; cloud must not use development default. |
| `SUPPORTED_CITY_IDS` | Optional, comma-separated override | Optional, comma-separated override | Empty/omitted falls back to configured default set. |
| `MANUAL_REVIEW_CONFIDENCE_THRESHOLD` | Optional float in `[0,1]` | Optional float in `[0,1]` | Must parse as probability and remain <= warn threshold. |
| `WARN_CONFIDENCE_THRESHOLD` | Optional float in `[0,1]` | Optional float in `[0,1]` | Must parse as probability and remain >= manual-review threshold. |
| `NEXT_PUBLIC_API_BASE_URL` | Required for frontend runtime | Required for frontend runtime | Must target active API endpoint for environment. |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | Required when enabling browser push | Required when enabling browser push | Missing key must disable push registration path, not crash unrelated flows. |

## Non-Negotiable Parity Rules

- One codebase: environment differences are configuration-driven only.
- No branch-specific business logic for local vs AWS behavior.
- Contracts for queue payloads, idempotency, retry outcomes, and observability labels are shared and versioned.
- Any intentional parity deviation must be documented with explicit compensating control before release.

## Related Contracts

- ST-009 notification event and dedupe contract: `docs/runbooks/st-009-notification-contract.md`
- ST-011 observability contract baseline: `docs/runbooks/st-011-observability-contract.md`
