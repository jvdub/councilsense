# ST-012 Behavior Parity Checklist

Use this checklist to validate the ST-012 parity architecture contract across local and AWS runtime paths.

## Core mapping coverage

- [ ] Local to AWS mapping is defined for `web`, `api`, `worker`, `db`, `storage`, and `queue`.
- [ ] Scheduler mapping is defined and uses equivalent enqueue intent contract.
- [ ] Auth, config/secrets, and observability mappings are documented.

## Idempotency parity

- [ ] Deterministic dedupe key contract is unchanged across environments.
- [ ] Duplicate enqueue path records duplicate/no-op outcome without creating a second logical send.
- [ ] Terminal delivery statuses remain terminal in both local and cloud.

## Retry + visibility parity

- [ ] Retry outcomes are limited to canonical contract labels.
- [ ] Retry behavior is bounded and configured through environment knobs only.
- [ ] Duplicate processing from at-least-once delivery does not violate logical idempotency.
- [ ] Visibility/eligibility behavior is adapter-specific but semantically equivalent (ready-only consumption).

## Startup dependency parity

- [ ] Web startup dependency checks pass/fail consistently by required env knobs.
- [ ] API startup fails fast on invalid auth/threshold config.
- [ ] Worker startup fails fast on invalid retry/idempotency configuration.
- [ ] Scheduler enqueues only enabled cities with deterministic cycle/run IDs.

## Configuration contract parity

- [ ] `AUTH_SESSION_SECRET` is non-empty in both environments.
- [ ] `SUPPORTED_CITY_IDS` parsing behavior matches in both environments.
- [ ] `MANUAL_REVIEW_CONFIDENCE_THRESHOLD` and `WARN_CONFIDENCE_THRESHOLD` parse and validate consistently.
- [ ] `NEXT_PUBLIC_API_BASE_URL` correctly targets the environment API.
- [ ] `NEXT_PUBLIC_VAPID_PUBLIC_KEY` gating behavior is consistent when push is enabled.

## Observability parity

- [ ] ST-011 required structured fields are emitted for parity-sensitive flows.
- [ ] Stage/outcome labels stay within closed enums for local and cloud.
- [ ] Notification enqueue/delivery metric names match canonical contract.

## Review sign-off

- [ ] Platform owner reviewed local↔AWS mapping and acceptable differences.
- [ ] Backend owner reviewed idempotency/retry/visibility parity constraints.
- [ ] Any deviation has a documented compensating control before release.
