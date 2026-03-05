# Phase 1.5: Additive evidence_references Contract

**Story ID:** ST-018  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** GAP_PLAN §Phase 1, GAP_PLAN §Gate A, MVP §4.5(1-2), FR-6, NFR-2

## User Story
As an API consumer, I want an additive `evidence_references` field in meeting detail payloads so evidence pointers are available without breaking existing integrations.

## Scope
- Expose additive `evidence_references` in meeting detail shaping and reader API responses.
- Preserve existing meeting detail fields and semantics unchanged.
- Add contract tests for presence/non-empty behavior based on evidence availability.

## Acceptance Criteria
1. Meeting detail payload includes additive `evidence_references` when evidence exists for summarized claims.
2. Existing payload fields and field semantics remain backward compatible for current consumers.
3. When evidence is absent or insufficient, payload behavior is explicit and contract-tested (empty/omitted according to established API pattern).
4. Contract tests validate both evidence-present and evidence-sparse fixtures.
5. Gate A contract-safety checks pass in local and CI test paths.

## Implementation Tasks
- [ ] Add additive meeting-detail payload projection for `evidence_references` in backend API shaping.
- [ ] Implement deterministic serialization format for evidence pointers used by reader responses.
- [ ] Add compatibility tests that assert unchanged legacy fields and additive-only delta.
- [ ] Add fixture-backed contract tests for evidence-present/evidence-sparse conditions.
- [ ] Add regression checks covering schema evolution safety for API consumers.

## Dependencies
- ST-006
- ST-017

## Definition of Done
- `evidence_references` is available as an additive payload element with backward compatibility preserved.
- Contract tests enforce API safety and evidence-availability behavior.
- Story outputs satisfy GAP_PLAN Gate A contract requirements.
