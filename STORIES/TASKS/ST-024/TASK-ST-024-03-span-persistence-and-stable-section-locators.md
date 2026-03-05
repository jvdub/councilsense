# Span Persistence and Stable Section Locators

**Task ID:** TASK-ST-024-03  
**Story:** ST-024  
**Bucket:** backend  
**Requirement Links:** ST-024 Acceptance Criteria #3 and #4, AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision, AGENDA_PLAN §4 Data model and contract changes (v1-first)

## Objective
Persist citation-ready spans for canonical documents with stable section paths and optional page/offset precision metadata.

## Scope
- Add span entities linked to canonical document and artifact contexts.
- Persist stable section path representation and optional page/index/offset fields.
- Define deterministic span ordering strategy used by downstream evidence references.
- Out of scope: claim-level evidence projection and API evidence v2 serialization.

## Inputs / Dependencies
- TASK-ST-024-01 canonical document persistence.
- TASK-ST-024-02 artifact persistence and lineage.
- Existing parser outputs for section/chunk extraction metadata.

## Implementation Notes
- Treat section path as canonical locator independent of parser chunk IDs.
- Keep optional precision fields nullable so low-precision sources still persist safely.
- Include parser-version metadata binding to spans for drift investigation.

## Acceptance Criteria
1. Span rows persist stable section-path metadata and optional page/offset precision fields.
2. Span records retain document and artifact lineage references.
3. Deterministic ordering exists for span selection and retrieval.
4. Schema remains additive and migration-safe.

## Validation
- Persist spans for minutes, agenda, and packet with representative precision profiles.
- Verify section-path stability across reruns of identical artifacts.
- Confirm optional precision fields do not block low-precision source writes.

## Deliverables
- Span schema + migration.
- Span repository/service persistence and retrieval contracts.
- Locator canonicalization rules for section path and precision metadata.
