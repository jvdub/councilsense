# Referential Integrity Integration Tests and Lineage Validation

**Task ID:** TASK-ST-024-05  
**Story:** ST-024  
**Bucket:** tests  
**Requirement Links:** ST-024 Acceptance Criteria #5, AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision, NFR-4

## Objective
Add integration coverage that proves referential integrity and retrieval correctness across canonical document -> artifact -> span entities.

## Scope
- Add integration tests for create/retrieve lifecycle across all three entity layers.
- Validate joins, constraints, and deterministic ordering for lineage traversal queries.
- Add regression tests for additive migration compatibility with pre-existing meeting records.
- Out of scope: frontend rendering and mismatch UI behavior.

## Inputs / Dependencies
- TASK-ST-024-04 pipeline write-path integration.
- Existing backend integration-test harness and fixture strategy.
- Pilot-city representative fixtures for minutes/agenda/packet combinations.

## Implementation Notes
- Include both full-source and partial-source fixtures to ensure resilient lineage behavior.
- Explicitly assert no orphan artifacts/spans and stable retrieval ordering across reruns.
- Preserve test determinism by pinning fixture checksums and parser metadata.

## Acceptance Criteria
1. Integration tests verify referential integrity from canonical document to artifact to span.
2. Test fixtures include minutes, agenda, and packet and validate cross-kind lifecycle behavior.
3. Rerun tests confirm deterministic retrieval and no duplicate lineage on unchanged input.
4. Additive migration compatibility is covered for legacy records.

## Validation
- `pytest -q backend/tests -k "canonical or artifact or span"`
- Run targeted pipeline integration suite with pilot-city fixture matrix.
- Capture test report artifacts for story completion evidence.

## Deliverables
- Integration test modules and fixtures for canonical persistence lineage.
- Deterministic rerun assertion coverage for document/artifact/span joins.
- Story-level validation evidence summary for AC #5.
