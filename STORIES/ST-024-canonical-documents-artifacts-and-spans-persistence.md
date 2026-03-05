# Agenda Plan: Canonical Documents, Artifacts, and Spans Persistence

**Story ID:** ST-024  
**Phase:** Phase 2 (Canonical persistence)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (normalization/storage), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision (Weeks 4–5)

## User Story
As a backend engineer, I want canonical document, artifact, and span persistence so evidence can be referenced with stable, document-aware locators.

## Scope
- Implement canonical meeting document persistence by kind/revision/authority metadata from AGENDA_PLAN section "Target architecture".
- Persist per-document raw/normalized artifacts and checksums from AGENDA_PLAN section "Data model and contract changes (v1-first)".
- Persist citation-ready spans with stable section paths and optional page/offset metadata from AGENDA_PLAN section "Phase 2 — Canonical document spans + evidence precision".

## Acceptance Criteria
1. Canonical document records exist for minutes, agenda, and packet with revision metadata.
2. Artifact records link to canonical documents and include checksum lineage.
3. Span records persist stable section path metadata and optional page/offset fields.
4. Persistence model is additive and does not require destructive migration.
5. Integration tests validate referential integrity across document → artifact → span.

## Implementation Tasks
- [ ] Implement canonical document tables/models and data-access layer updates.
- [ ] Implement artifact persistence and checksum lineage fields.
- [ ] Implement span persistence with section path and precision metadata.
- [ ] Backfill or migration hooks for initial pilot-city documents.
- [ ] Add integration tests for entity lifecycle and joins.

## Dependencies
- ST-022
- ST-023

## Definition of Done
- Canonical document and span persistence is production-ready for pipeline usage.
- Data model remains additive and migration-safe for pre-launch iteration.
- Tests validate lineage integrity and retrieval correctness.
