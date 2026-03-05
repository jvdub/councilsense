# Claim-to-Canonical Document/Span Linkage Contract

**Task ID:** TASK-ST-026-01  
**Story:** ST-026  
**Bucket:** data  
**Requirement Links:** ST-026 Acceptance Criteria #1, AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision

## Objective

Define and implement the additive linkage contract that attaches claim evidence to canonical document and span references with precision/confidence metadata.

## Scope

- Define required and optional linkage fields for document kind, section path, span/offset, precision, and confidence.
- Ensure linkage supports canonical document/span identifiers produced by upstream extraction.
- Define nullability and safe-omit behavior when precision metadata is unavailable.
- Out of scope: deterministic ranking logic, API serializer output ordering, and diagnostics reporting.

## Inputs / Dependencies

- ST-018 additive evidence references contract shape.
- ST-024 canonical span persistence model.
- ST-025 multi-source authority alignment artifacts.

## Implementation Notes

- Keep schema additive so legacy evidence fields remain non-blocking during migration.
- Use stable field naming compatible with `evidence_references_v2` projection.
- Treat malformed or partial span metadata as explicit lower-precision references, not dropped evidence.

## Acceptance Criteria

1. Claim evidence records can reference canonical documents and spans with precision metadata.
2. Linkage fields include document kind, section path, precision, and confidence metadata.
3. Missing span-level details safely degrade to lower-precision linkage without breaking output generation.
4. Linkage contract is documented as additive and backward-safe.

## Validation

- Run schema/model tests for canonical document/span linkage records.
- Validate fixture records with full-span, section-only, and file-level fallback cases.
- Confirm legacy evidence consumers remain functional when new fields are absent.

## Deliverables

- Additive linkage contract for claim evidence to canonical document/span references.
- Model/schema update notes for precision/confidence metadata fields.
- Fallback behavior examples for incomplete precision metadata.
