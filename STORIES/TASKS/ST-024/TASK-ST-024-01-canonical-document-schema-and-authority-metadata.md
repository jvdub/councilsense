# Canonical Document Schema and Authority Metadata

**Task ID:** TASK-ST-024-01  
**Story:** ST-024  
**Bucket:** data  
**Requirement Links:** ST-024 Acceptance Criteria #1 and #4, AGENDA_PLAN §3 Target architecture (normalization/storage), AGENDA_PLAN §4 Data model and contract changes (v1-first)

## Objective
Add additive canonical-document persistence for minutes, agenda, and packet with revision and authority metadata required for downstream artifact/span lineage.

## Scope
- Define canonical document entities keyed by meeting and document kind (minutes, agenda, packet).
- Persist revision/version, authority metadata, parser metadata, and extraction-status fields.
- Add constraints/indexes that enforce one deterministic active revision selection strategy without destructive migration.
- Out of scope: artifact payload persistence, span persistence, and summarization policy logic.

## Inputs / Dependencies
- ST-022 contract freeze decisions for v1 shape and additive evolution.
- ST-023 meeting bundle planner outputs and source-kind normalization.
- Existing migration conventions and model registry under backend schema layers.

## Implementation Notes
- Preserve backward compatibility for existing records by using nullable/additive columns and non-breaking defaults.
- Represent authority metadata explicitly so minutes-authoritative behavior can be resolved without source guessing.
- Include migration notes for pilot cities with existing single-source minutes records.

## Acceptance Criteria
1. Canonical document rows persist minutes, agenda, and packet kinds with revision metadata.
2. Authority metadata is explicitly represented and queryable for each canonical document.
3. Schema/index choices support deterministic retrieval of the current revision.
4. Migration plan is additive and does not require destructive changes.

## Validation
- Run schema migration and rollback smoke checks in local runtime.
- Verify create/read/update flows for canonical documents across all three kinds.
- Confirm legacy meeting records remain readable after additive migration.

## Deliverables
- Canonical document schema + migration.
- Data-access layer interfaces for canonical document create/read/update.
- Migration/backfill notes for pilot-city compatibility.
