# Agenda Plan: Evidence v2 Linkage, Precision Ladder, and Deterministic Ordering

**Story ID:** ST-026  
**Phase:** Phase 2 (Evidence precision)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision (Weeks 4–5), AGENDA_PLAN §6 Testing and validation plan

## User Story

As a reader, I want stable and precise evidence references so I can verify claims quickly and consistently across reruns.

## Scope

- Link claim evidence to canonical document/span references from AGENDA_PLAN section "Phase 2 — Canonical document spans + evidence precision".
- Implement precision ladder and deterministic ordering (offset > span > section > file) from AGENDA_PLAN section "Target architecture (summarization)".
- Expose additive `evidence_references_v2` projection as primary evidence shape; legacy mapping remains optional and non-blocking.

## Acceptance Criteria

1. Evidence references include document kind, section path, precision, and confidence metadata.
2. Evidence ordering is deterministic across reruns for identical source inputs.
3. Majority of references are finer than file-level where parser precision metadata is present.
4. API contract fixtures validate stable `evidence_references_v2` shape.
5. Optional compatibility mapping can be disabled without blocking release readiness.

## Implementation Tasks

- [ ] Implement claim-to-document/span linkage in summarization output model.
- [ ] Implement precision ranking and deterministic ordering logic.
- [ ] Implement additive evidence v2 projection in publication/read models.
- [ ] Add contract fixtures and snapshot tests for evidence v2.
- [ ] Add precision-distribution diagnostics for scorecard/ops reporting.

## Dependencies

- ST-018
- ST-024
- ST-025

## Definition of Done

- Evidence v2 is stable, additive, and deterministic.
- Precision ladder behavior is measurable and validated by tests.
- Release path does not depend on mandatory backward-compatibility shims.
