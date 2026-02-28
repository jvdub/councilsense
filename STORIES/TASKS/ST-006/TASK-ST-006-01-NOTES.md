# TASK-ST-006-01 Contract Notes

## Canonical Meeting List Ordering

- Primary sort: `meetings.created_at DESC`
- Tie-breaker sort: `meetings.id DESC`
- This ordering is stable and deterministic across repeated requests.

## Cursor Contract

- Cursor payload fields:
  - `created_at` (string timestamp)
  - `meeting_id` (string)
- Cursor predicate for next page:
  - `created_at < cursor.created_at`
  - OR `created_at == cursor.created_at AND id < cursor.meeting_id`

## List Projection Fields (Read Model Prep)

- `id`
- `city_id`
- `meeting_uid`
- `title`
- `created_at`
- `updated_at`
- `publication_status` (latest publication for meeting, nullable)
- `confidence_label` (latest publication for meeting, nullable)

## Query Path Indexes

- `idx_meetings_city_created_id` on `(city_id, created_at DESC, id DESC)`
- `idx_summary_publications_meeting_published_id` on `(meeting_id, published_at DESC, id DESC)`
