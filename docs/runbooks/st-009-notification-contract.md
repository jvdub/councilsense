# ST-009 Notification Event Contract and Dedupe Key

## Scope and Version

- Canonical contract for notification fan-out enqueue payloads and delivery-worker processing.
- Contract version: `st-009-v1`
- Dedupe key version prefix: `notif-dedupe-v1`

## Event Payload Contract (v1)

### Required fields

| Field | Type | Description |
| --- | --- | --- |
| `contract_version` | `string` | Must equal `st-009-v1`. |
| `user_id` | `string` | Non-empty user identifier. |
| `meeting_id` | `string` | Non-empty meeting identifier. |
| `notification_type` | `string` | Non-empty notification class (example: `meeting_published`). |
| `dedupe_key` | `string` | Deterministic key derived from `user_id + meeting_id + notification_type`. |
| `enqueued_at` | `string` (ISO-8601 with timezone) | Event enqueue timestamp. |
| `delivery_status` | `string` enum | One of: `queued`, `sending`, `sent`, `failed`, `suppressed`, `invalid_subscription`, `expired_subscription`. |
| `attempt_count` | `integer` | Attempt count, `>= 0`. |

### Optional fields

| Field | Type | Description |
| --- | --- | --- |
| `subscription_id` | `string \| null` | Subscription used for a specific delivery attempt. |
| `error_code` | `string \| null` | Worker/system error code for failed/suppressed cases. |

## Deterministic Dedupe Key

Algorithm (v1):

1. Normalize string inputs by trimming whitespace.
2. Lowercase `notification_type`.
3. Join: `user_id`, `meeting_id`, `notification_type` with unit separator (`\x1f`).
4. Compute `sha256` hex digest.
5. Emit key: `notif-dedupe-v1:<digest>`.

Properties:

- Deterministic for identical input triples.
- Distinct triples produce distinct keys for story scope.
- Opaque key format avoids delimiter-collision ambiguity in raw IDs.

## Delivery Lifecycle Status Model

| Current | Allowed Next |
| --- | --- |
| `queued` | `sending`, `suppressed`, `invalid_subscription`, `expired_subscription` |
| `sending` | `sent`, `failed`, `suppressed`, `invalid_subscription`, `expired_subscription` |
| `failed` | `sending`, `suppressed`, `invalid_subscription`, `expired_subscription` |
| `sent` | terminal |
| `suppressed` | terminal |
| `invalid_subscription` | terminal |
| `expired_subscription` | terminal |

Notes:

- `invalid_subscription`: endpoint/token is malformed, revoked, or permanently unusable.
- `expired_subscription`: endpoint/token expired and requires client re-registration.
- Both states are terminal for the current dedupe key and prevent repeated sends for the same `(user_id, meeting_id, notification_type)` tuple.
