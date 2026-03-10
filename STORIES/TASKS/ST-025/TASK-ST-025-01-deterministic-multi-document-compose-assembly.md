# Deterministic Multi-Document Compose Assembly

**Task ID:** TASK-ST-025-01  
**Story:** ST-025  
**Bucket:** backend  
**Requirement Links:** ST-025 Acceptance Criteria #1 and #4, AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §5 Phase 1

## Objective

Build the summarize compose step that assembles available canonical documents in deterministic source order for each meeting publication attempt.

## Scope

- Define compose input contract for minutes, agenda, and packet canonical sources.
- Implement deterministic source ordering and tie-break behavior across revisions.
- Include source-coverage metadata in compose output for downstream confidence policy.
- Out of scope: authority conflict resolution and publish-state transition logic.

## Inputs / Dependencies

- ST-023 meeting bundle/source-scoped ingestion outputs.
- ST-024 canonical document and artifact persistence contracts.
- Existing summarize pipeline entry points and payload models.

## Implementation Notes

- Determinism should hold across reruns with identical persisted source sets.
- Compose must support partial-source meetings without hard failure.
- Record missing-source diagnostics for confidence policy evaluation.

## Acceptance Criteria

1. Compose includes all available canonical documents for a meeting in deterministic order.
2. Compose behavior is stable across reruns with unchanged source inputs.
3. Source-coverage metadata is available for downstream limited-confidence evaluation.
4. Partial-source meetings continue through compose without suppression.

## Validation

- Run compose tests with full-source and partial-source fixture matrices.
- Verify ordering stability across repeated executions.
- Confirm source-coverage diagnostics match fixture expectations.

## Deliverables

- Compose assembler contract and implementation notes.
- Deterministic ordering rules for source/revision selection.
- Source-coverage diagnostic payload fields.
