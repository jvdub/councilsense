# Additive `evidence_references_v2` Projection and Compatibility Gating

**Task ID:** TASK-ST-026-03  
**Story:** ST-026  
**Bucket:** backend  
**Requirement Links:** ST-026 Acceptance Criteria #1, #4, #5, AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision

## Objective

Expose additive `evidence_references_v2` as the primary evidence projection while keeping legacy compatibility mapping optional and non-blocking.

## Scope

- Add `evidence_references_v2` projection wiring in publication/read models.
- Define optional compatibility mapping behavior for legacy evidence shapes.
- Add feature/rollout control to disable compatibility mapping without release blocker impact.
- Out of scope: frontend rendering changes and API planned/outcomes additive fields.

## Inputs / Dependencies

- TASK-ST-026-01 linkage contract fields.
- TASK-ST-026-02 deterministic ordering behavior.
- ST-018 additive evidence references compatibility context.

## Implementation Notes

- Treat `evidence_references_v2` as canonical output shape for new clients.
- Keep compatibility mapping additive and toggleable, not required for release readiness.
- Ensure omission behavior is explicit when v2 references are unavailable.

## Acceptance Criteria

1. Publication/read models expose additive `evidence_references_v2` blocks.
2. V2 fields include document kind, section path, precision, and confidence metadata when available.
3. Legacy mapping can be disabled without blocking release readiness.
4. Projection behavior remains backward-safe for clients not consuming v2 fields.

## Validation

- Execute projection tests for v2-present, v2-partial, and v2-absent scenarios.
- Verify compatibility mode on/off behavior with unchanged publish readiness outcome.
- Validate projection ordering follows deterministic ranking from TASK-ST-026-02.

## Deliverables

- Additive `evidence_references_v2` projection contract in publication/read models.
- Compatibility gating behavior definition and rollout defaults.
- Example payloads for compatibility-on and compatibility-off modes.
