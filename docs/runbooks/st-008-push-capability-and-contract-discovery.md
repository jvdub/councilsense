# ST-008 Push Capability + Subscription Contract Discovery

**Date:** 2026-02-27  
**Story:** ST-008  
**Task:** TASK-ST-008-01  
**Requirement Links:** MVP §4.4(2-5), FR-5(4-5), NFR-3

## Decisions (Locked for MVP)

- Channel scope is web push only for MVP.
- Push UX must degrade to deterministic non-subscribe states when capability is missing or permission is denied.
- Subscription lifecycle API contract is self-service under `/v1/me/push-subscriptions`.
- Delivery state flags `invalid`, `expired`, and `suppressed` are distinct and map to explicit recovery actions.

## Browser Capability Matrix

| Capability state | Service worker | PushManager | Notification permission | UX state | Action |
| --- | --- | --- | --- | --- | --- |
| Fully supported + granted | yes | yes | granted | `subscribable` | Show subscribe/unsubscribe controls and call subscription API |
| Supported but default permission | yes | yes | default | `permission_required` | Show "Enable push" action, request permission on user gesture |
| Supported but denied permission | yes | yes | denied | `permission_denied` | Show blocked state and browser-settings recovery guidance |
| Missing PushManager support | yes | no | any | `unsupported` | Hide subscribe CTA; show unsupported fallback copy |
| Missing service worker support | no | any | any | `unsupported` | Hide subscribe CTA; show unsupported fallback copy |
| Non-secure context | n/a | n/a | any | `unsupported` | Do not attempt registration; show secure-context requirement copy |

### Fallback behavior

- `unsupported`: do not attempt permission prompts or API mutation calls.
- `permission_denied`: do not retry prompt loops; only provide a manual recovery path.
- `permission_required`: request permission only from explicit user interaction (button click), never on page load.

## Push Subscription API Contract (MVP)

Base path: `/v1/me/push-subscriptions`

### 1) List subscriptions

- Method: `GET /v1/me/push-subscriptions`
- Purpose: fetch current user subscriptions and server-side state flags.

Response `200`:

```json
{
  "items": [
    {
      "id": "psub_123",
      "endpoint": "https://push.example/sub/abc",
      "keys": {
        "p256dh": "base64url",
        "auth": "base64url"
      },
      "status": "active",
      "failure_reason": null,
      "last_seen_at": "2026-02-27T17:00:00Z",
      "created_at": "2026-02-25T12:00:00Z",
      "updated_at": "2026-02-27T17:00:00Z"
    }
  ]
}
```

### 2) Create or upsert subscription

- Method: `POST /v1/me/push-subscriptions`
- Purpose: create a new subscription or idempotently refresh existing endpoint+keys tuple.
- Idempotency key: derived server-side from authenticated `user_id + endpoint`.

Request:

```json
{
  "endpoint": "https://push.example/sub/abc",
  "keys": {
    "p256dh": "base64url",
    "auth": "base64url"
  },
  "user_agent": "optional",
  "device_label": "optional"
}
```

Response `201` on create or `200` on refresh:

```json
{
  "id": "psub_123",
  "status": "active",
  "failure_reason": null
}
```

### 3) Delete subscription

- Method: `DELETE /v1/me/push-subscriptions/{subscription_id}`
- Purpose: unsubscribe current browser/device record.

Response `204` (idempotent; deleting an already removed record remains `204`).

### 4) State enums

- `active`: eligible for send attempts.
- `invalid`: endpoint rejected permanently by provider.
- `expired`: endpoint no longer valid and must be re-subscribed.
- `suppressed`: intentionally not attempted (policy guardrail after repeated hard failures).

## Recovery Mapping (State -> UX Action)

| Server state | Meaning | Recovery action |
| --- | --- | --- |
| `invalid` | provider indicates endpoint is unusable | Re-run browser subscribe flow and `POST` new subscription |
| `expired` | endpoint aged out or rotated | Re-run browser subscribe flow and `POST` refresh |
| `suppressed` | server temporarily blocks sends after repeated failures | Offer explicit "Reactivate push" action that performs unsubscribe + new subscribe |

## Ownership Sign-off Targets

- Frontend owner confirms matrix + permission UX states are implementation-ready.
- Backend owner confirms endpoint contract and state enum semantics.
- No unresolved MVP blocker remains for ST-008 implementation tasks.