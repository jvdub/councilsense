# ST-022 Additive Schema Specification and Migration Sequence Plan

- Story: ST-022
- Task: TASK-ST-022-02
- Scope: additive schema only (no destructive actions)
- Contract alignment: `st-022-meeting-detail-v1` (`planned`, `outcomes`, `planned_outcome_mismatches`, `evidence_references_v2`)

## Purpose

Define the additive schema units and migration order required to support canonical documents, artifacts, spans, and publication/source-coverage aggregates for agenda-plan v1.

## Additive schema specification

All additions below are additive and nullable-by-default on first introduction unless noted otherwise.

### 1) Canonical documents

Create `meeting_canonical_documents`.

| Column                  | Type        | Required | Notes                                          |
| ----------------------- | ----------- | -------- | ---------------------------------------------- |
| `id`                    | UUID        | yes      | Primary key.                                   |
| `meeting_id`            | UUID        | yes      | FK to meetings table.                          |
| `document_kind`         | text enum   | yes      | Allowed values: `minutes`, `agenda`, `packet`. |
| `source_uri`            | text        | no       | Original source locator, if available.         |
| `revision`              | integer     | yes      | Monotonic per (`meeting_id`, `document_kind`). |
| `checksum`              | text        | yes      | Canonical content checksum used for dedupe.    |
| `authority_rank`        | smallint    | yes      | `minutes` highest, then `agenda`/`packet`.     |
| `parser_version`        | text        | yes      | Parser identity/version used for extraction.   |
| `extraction_status`     | text enum   | yes      | `succeeded`, `partial`, `failed`.              |
| `extraction_confidence` | text enum   | yes      | `high`, `medium`, `low`.                       |
| `created_at`            | timestamptz | yes      | Default now().                                 |
| `updated_at`            | timestamptz | yes      | Default now().                                 |

Constraints and indexes:

- Unique: (`meeting_id`, `document_kind`, `revision`).
- Unique: (`meeting_id`, `document_kind`, `checksum`) for deterministic dedupe.
- Index: (`meeting_id`, `document_kind`, `created_at` desc) for latest-per-kind lookup.

### 2) Canonical document artifacts

Create `meeting_document_artifacts`.

| Column                  | Type        | Required | Notes                                   |
| ----------------------- | ----------- | -------- | --------------------------------------- |
| `id`                    | UUID        | yes      | Primary key.                            |
| `canonical_document_id` | UUID        | yes      | FK to `meeting_canonical_documents.id`. |
| `artifact_type`         | text enum   | yes      | `raw`, `normalized`, `structured`.      |
| `storage_uri`           | text        | yes      | Blob/object path.                       |
| `mime_type`             | text        | no       | Media type where known.                 |
| `byte_size`             | bigint      | no       | Optional artifact size.                 |
| `checksum`              | text        | yes      | Artifact checksum.                      |
| `created_at`            | timestamptz | yes      | Default now().                          |

Constraints and indexes:

- Unique: (`canonical_document_id`, `artifact_type`, `checksum`).
- Index: (`canonical_document_id`, `artifact_type`).
- Index: (`checksum`) for dedupe inspection.

### 3) Citation spans

Create `meeting_document_spans`.

| Column                  | Type        | Required | Notes                                                                              |
| ----------------------- | ----------- | -------- | ---------------------------------------------------------------------------------- |
| `id`                    | UUID        | yes      | Primary key.                                                                       |
| `canonical_document_id` | UUID        | yes      | FK to `meeting_canonical_documents.id`.                                            |
| `artifact_id`           | UUID        | no       | FK to `meeting_document_artifacts.id` when span comes from specific artifact form. |
| `section_path`          | text        | yes      | Deterministic hierarchical locator.                                                |
| `span_label`            | text        | no       | Optional semantic label.                                                           |
| `page_start`            | integer     | no       | Optional page range start.                                                         |
| `page_end`              | integer     | no       | Optional page range end.                                                           |
| `char_start`            | integer     | no       | Optional character start offset.                                                   |
| `char_end`              | integer     | no       | Optional character end offset.                                                     |
| `excerpt`               | text        | no       | Optional clipped text.                                                             |
| `created_at`            | timestamptz | yes      | Default now().                                                                     |

Constraints and indexes:

- Check: `page_end >= page_start` when both are non-null.
- Check: `char_end >= char_start` when both are non-null.
- Unique: (`canonical_document_id`, `section_path`, `page_start`, `char_start`) to keep locator determinism.
- Index: (`canonical_document_id`, `section_path`).

### 4) Evidence linkage extensions

Extend existing evidence-reference persistence (or claim evidence table) with additive nullable columns:

- `canonical_document_id` (UUID FK)
- `artifact_id` (UUID FK)
- `span_id` (UUID FK)
- `document_kind` (text enum: `minutes`/`agenda`/`packet`)
- `precision` (text enum: `offset`/`span`/`section`/`file`)

Indexes:

- Index: (`publication_id`, `document_kind`).
- Index: (`publication_id`, `precision`).

### 5) Publication/source-coverage aggregates

Create `publication_source_coverage_aggregates`.

| Column                    | Type        | Required | Notes                                     |
| ------------------------- | ----------- | -------- | ----------------------------------------- |
| `id`                      | UUID        | yes      | Primary key.                              |
| `publication_id`          | UUID        | yes      | FK to publication/summary table.          |
| `minutes_status`          | text enum   | yes      | `present`, `missing`, `partial`.          |
| `agenda_status`           | text enum   | yes      | `present`, `missing`, `partial`.          |
| `packet_status`           | text enum   | yes      | `present`, `missing`, `partial`.          |
| `coverage_ratio`          | numeric     | no       | Optional computed ratio (0..1).           |
| `precision_offset_count`  | integer     | yes      | Count of offset precision evidence refs.  |
| `precision_span_count`    | integer     | yes      | Count of span precision evidence refs.    |
| `precision_section_count` | integer     | yes      | Count of section precision evidence refs. |
| `precision_file_count`    | integer     | yes      | Count of file precision evidence refs.    |
| `created_at`              | timestamptz | yes      | Default now().                            |

Constraints and indexes:

- Unique: (`publication_id`).
- Check: `coverage_ratio` between 0 and 1 when non-null.
- Index: (`minutes_status`, `agenda_status`, `packet_status`) for ops filtering.

## Ordered migration sequence (rollback-safe, additive only)

Order is intentionally progressive so each step can be safely rolled back by disabling writes/readers, not by dropping schema.

1. Create additive enums/check domains if needed (`document_kind`, `precision`, status values).
2. Create `meeting_canonical_documents` with PK/FK and non-destructive indexes.
3. Create `meeting_document_artifacts` with FK to canonical documents.
4. Create `meeting_document_spans` with FK and locator constraints.
5. Add nullable evidence-link columns and indexes to existing evidence table(s).
6. Create `publication_source_coverage_aggregates` and required indexes.
7. Deploy write path behind feature flags; default read behavior remains baseline.
8. Backfill in bounded batches: canonical docs -> artifacts -> spans -> evidence links -> coverage aggregates.
9. Enable additive reads/projections after backfill validation; keep old projections intact during coexistence.

## Rollback-safe ordering rules

- Never remove or rename existing columns/tables in this sequence.
- New columns are introduced nullable first; any future NOT NULL tightening is deferred to a post-freeze task.
- New readers are enabled only after writers are live and backfill passes.
- Rollback action is flag disablement and write pause, not schema reversal.
- Backfill jobs are idempotent via dedupe keys (`meeting_id`, `document_kind`, `checksum`) and checkpointed batches.

## Explicit destructive-change prohibitions for TASK-ST-022-02

Disallowed in this task scope:

- `DROP TABLE`, `DROP COLUMN`, `DROP INDEX` on existing baseline objects.
- Column/type rewrites that invalidate existing data contracts.
- Renaming legacy fields relied on by ST-006/ST-018 clients.
- Hard deletes in migration SQL for historical publication/evidence records.

## Validation checklist

- Confirm additive-only migration content (no destructive DDL).
- Confirm unique/index strategy supports deterministic dedupe and lookup paths.
- Confirm field coverage for v1 evidence references (`document_kind`, locator precision, provenance links).
- Confirm publish/source-coverage aggregate supports `planned.source_coverage` semantics.
