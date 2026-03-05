# Additive Schema and Migration Sequence Plan

**Task ID:** TASK-ST-022-02  
**Story:** ST-022  
**Bucket:** data  
**Requirement Links:** ST-022 Scope (additive schema changes), ST-022 Acceptance Criteria #2, AGENDA_PLAN §4

## Objective
Define an additive-only database migration plan for canonical documents, artifacts, spans, and publication/source-coverage aggregates required by the v1 agenda plan.

## Scope
- Specify new/extended tables and columns for canonical documents, artifacts, spans, and publication aggregates.
- Define migration sequencing, backfill posture (if any), and index/constraint strategy.
- Document explicit destructive-change prohibitions for this phase.
- Out of scope: full migration implementation and production rollout execution.

## Inputs / Dependencies
- TASK-ST-022-01 v1 contract fields and fixture semantics.
- Existing DB conventions and migration workflow in backend.
- AGENDA_PLAN additive model guidance.

## Implementation Notes
- Include source-kind, revision, checksum, precision, and provenance requirements where relevant.
- Mark each schema addition with rationale and consumer usage (ingestion, summarization, API projection, observability).
- Add rollback-safe notes for additive migrations.

## Acceptance Criteria
1. Schema plan covers canonical documents, artifacts, spans, and publication/source-coverage aggregates. (ST-022 Scope)
2. Migration sequence is additive-only and explicitly non-destructive. (ST-022 AC #2)
3. Constraints/indexes needed for deterministic dedupe and lookups are documented. (ST-022 AC #2)

## Validation
- Peer review migration sequence for additive-only compliance.
- Verify no drop/rename-destructive operations are present in plan.
- Confirm schema supports fields required by v1 fixtures.

## Deliverables
- Additive schema specification document.
- Ordered migration sequence plan with safety notes.
- Constraint/index matrix tied to ingestion and API use cases.
