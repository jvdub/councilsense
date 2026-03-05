# Artifact Lineage and Checksum Persistence

**Task ID:** TASK-ST-024-02  
**Story:** ST-024  
**Bucket:** data  
**Requirement Links:** ST-024 Acceptance Criteria #2 and #4, AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision

## Objective
Persist raw/normalized artifacts linked to canonical documents, including checksum lineage that supports dedupe and traceability.

## Scope
- Add artifact entities linked to canonical document IDs for raw and normalized payload variants.
- Persist checksum fields and lineage metadata used to trace transformation ancestry.
- Add repository/data-access methods for deterministic artifact upsert and retrieval by checksum.
- Out of scope: span extraction/persistence and confidence policy behavior.

## Inputs / Dependencies
- TASK-ST-024-01 canonical document tables and authority metadata.
- ST-023 source-scoped ingestion checksum/dedupe behavior.
- Existing artifact storage conventions (raw object references and normalized forms).

## Implementation Notes
- Keep lineage additive: preserve prior artifact versions instead of overwriting historical rows.
- Ensure checksum uniqueness semantics are explicit (global vs per-document scoping).
- Include metadata for parser/normalizer version association to support drift diagnostics.

## Acceptance Criteria
1. Artifact rows are linked to canonical documents with referential integrity.
2. Raw and normalized forms can be represented with checksum lineage.
3. Artifact retrieval by canonical-document + checksum is deterministic.
4. Additive migration strategy preserves existing ingest artifacts.

## Validation
- Execute ingest replay for identical source content and verify dedupe behavior.
- Verify artifact lineage chain queries return expected ancestry.
- Confirm referential constraints prevent orphan artifact writes.

## Deliverables
- Artifact schema + migration updates.
- Artifact repository/service interfaces for linked persistence and lookup.
- Checksum lineage query examples for diagnostics and audits.
