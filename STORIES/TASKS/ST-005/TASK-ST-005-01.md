# Summary/Evidence Persistence Schema

**Task ID:** TASK-ST-005-01  
**Story:** ST-005  
**Bucket:** data  
**Requirement Links:** MVP §4.3(2-4), FR-4, FR-7(3), NFR-4, NFR-7

## Objective
Define the persisted data contract for summary output, claim evidence pointers, confidence state, and provenance-ready publish records.

## Scope (+ Out of scope)
- Add/adjust schema fields for summary, key decisions/actions, notable topics.
- Add claim evidence fields: artifact_id, section/offset reference, excerpt.
- Add publish confidence state fields supporting `processed` and `limited_confidence`.
- Out of scope: generation logic and API response formatting.

## Inputs / Dependencies
- Story spec ST-005.
- Existing meeting/artifact/provenance schema.
- No task dependencies.

## Implementation Notes
- Keep evidence structure normalized and queryable.
- Preserve backward compatibility for existing processed meetings.
- Model confidence fields so UI/API can render labels without recomputation.

## Acceptance Criteria
1. Schema supports all required output sections and claim-level evidence pointers.
2. Evidence fields explicitly store artifact_id, section/offset, and excerpt.
3. Confidence state can represent `processed` and `limited_confidence`.
4. Migration is safe for existing records.

## Validation
- Run migration and schema validation checks in local dev DB.
- Run targeted persistence tests for meeting read/write models.

## Deliverables
- Migration(s) and updated data model definitions.
- Short schema note documenting confidence and evidence fields.
