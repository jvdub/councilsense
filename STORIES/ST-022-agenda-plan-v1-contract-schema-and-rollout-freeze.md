# Agenda Plan: v1 Contract, Schema, and Rollout Freeze

**Story ID:** ST-022  
**Phase:** Phase 0 (Contract and schema freeze)  
**Requirement Links:** AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 0 — Contract and schema freeze (Week 1), AGENDA_PLAN §10 Decision log and open questions

## User Story

As a platform owner, I want a frozen v1 contract/schema and rollout control matrix so implementation teams can deliver agenda+packet+minutes support without contract churn.

## Scope

- Define and freeze clean v1 payloads for `planned`, `outcomes`, `planned_outcome_mismatches`, and `evidence_references_v2` from AGENDA_PLAN section "Data model and contract changes (v1-first)".
- Define additive database schema changes for canonical documents, artifacts, spans, and publication/source-coverage aggregates from AGENDA_PLAN section "Data model and contract changes (v1-first)".
- Define rollout flag matrix and rollback order from AGENDA_PLAN section "Decision log and open questions".
- Document legacy compatibility shim options as optional and explicitly non-blocking for pre-launch delivery.

## Acceptance Criteria

1. Versioned v1 contract spec and fixtures are approved and checked into repo docs.
2. Schema migration plan is additive-only and explicitly avoids destructive changes.
3. Rollout/rollback matrix is documented with flag names, default states, and reversal order.
4. Compatibility mapping scope is documented as optional and not a release blocker.
5. Open contract questions are either resolved or tracked with owners and due dates.

## Implementation Tasks

- [x] Author v1 API contract spec for planned/outcomes/mismatch/evidence v2 shapes.
- [x] Author additive schema spec and migration sequence for canonical document entities.
- [x] Define idempotency key naming rules and stage ownership table.
- [x] Define rollout flag matrix and rollback sequence documentation.
- [x] Create and review contract fixtures for backend/frontend tests.

## Dependencies

- None

## Definition of Done

- Contract and schema are frozen for implementation phases.
- Fixture set reflects approved v1 contract and additive schema assumptions.
- Rollout controls are documented and usable by engineering and operations.
