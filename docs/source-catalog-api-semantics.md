# Source Catalog API Semantics

This document freezes the additive reader contract introduced in ST-037 and the admission-control semantics added in ST-038 for discovered meetings and processing requests.

## City Meetings List

Endpoint:

```text
GET /v1/cities/{city_id}/meetings
```

The response remains city-scoped and additive. Existing processed-meeting consumers can continue using the legacy top-level fields, while new consumers can read discovered-meeting and processing-state projection fields.

### Additive fields

Each list item now includes:

- `meeting_id`: local meeting identifier when a discovered meeting has already been reconciled to a local meeting row.
- `detail_available`: `true` when a local meeting detail route can be resolved.
- `discovered_meeting`: provider/source identity and sync timestamps for the discovered-meeting registry row.
- `processing`: user-visible processing projection.

### User-visible processing states

The `processing.processing_status` field is frozen to the following values:

- `discovered`: the meeting is present in the discovered-meetings registry but no active or terminal on-demand request exists.
- `queued`: an on-demand processing run exists for the discovered meeting and its linked ingest-stage work has not started yet.
- `processing`: active local work exists and the linked ingest-stage work has started, or the item is a legacy local meeting row without a terminal publication yet.
- `processed`: a publication exists, including `limited_confidence` publications.
- `failed`: the latest processing request reached a terminal failure state.

The legacy `status` field is still the publication status projection. It is intentionally not the same thing as `processing.processing_status`.

### Filtering semantics

The `status` query parameter on `GET /v1/cities/{city_id}/meetings` now filters on the user-visible `processing.processing_status` field rather than the legacy publication-only status field.

Example:

- `status=processed` returns both fully processed and limited-confidence published meetings.

## Processing Request Endpoint

Endpoint:

```text
POST /v1/cities/{city_id}/meetings/{discovered_meeting_id}/processing-request
```

This endpoint is authenticated and home-city scoped. A user cannot request processing for a discovered meeting outside their configured home city.

### Queue-or-return behavior

The endpoint guarantees meeting-level idempotency for active work and binds resident-triggered requests to the existing processing run and stage lifecycle.

- If no active request exists for the discovered meeting, the API creates one and returns `201`.
- If an active request already exists for the same discovered meeting, the API returns that existing request and returns `200`.

The response always includes a `processing.request_outcome` field with one of:

- `queued`: a new request was created by this call.
- `already_active`: the API returned the existing active request instead of creating another one.

### Error semantics

- `403`: the authenticated user attempted to access a city outside their home-city scope.
- `404`: the discovered meeting does not exist for the requested city.
- `409`: the discovered meeting is already backed by a published local meeting and does not need another request.
- `429`: the authenticated user exceeded configured on-demand admission-control limits for active work. Duplicate requests for the same already-active meeting still return `200` with `already_active` rather than failing this limit check.

## ST-038 Admission Control

ST-038 adds bounded resident-facing admission control on top of the queue-or-return contract.

- Meeting-level dedupe wins first: repeat clicks for the same active discovered meeting converge on the same work item.
- Per-user limits apply only when the request would create a new active work item.
- Terminal failed attempts can open a new request attempt, and that new request preserves lineage back to the prior terminal attempt.
