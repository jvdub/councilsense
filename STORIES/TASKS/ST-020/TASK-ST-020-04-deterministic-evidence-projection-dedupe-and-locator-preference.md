# Deterministic Evidence Projection, Dedupe, and Locator Preference

**Task ID:** TASK-ST-020-04  
**Story:** ST-020  
**Bucket:** backend  
**Requirement Links:** FR-4, GAP_PLAN §Parity Targets (Evidence precision, Grounding), GAP_PLAN §Gate B

## Objective

Harden evidence projection so pointers are deterministic, deduplicated, and prefer finer-grained locators when subsection/offset data exists.

## Scope

- Implement deterministic ordering and dedupe rules for `evidence_references` projection.
- Prefer subsection/offset locators over file-level pointers when parser-provided precision is available.
- Preserve compatibility with additive evidence reference contract from ST-018.
- Out of scope: introducing new pointer fields not already supported by existing contracts.

## Inputs / Dependencies

- TASK-ST-020-02 anchor extraction outputs.
- Existing evidence reference projection behavior and ST-018 contract constraints.

## Implementation Notes

- Define equivalence rules for pointer dedupe explicitly (same file/section/offset semantics).
- Keep ranking deterministic to avoid rerun drift in API payloads and scorecard evidence.
- Where fine-grained locator data is unavailable, retain current fallback behavior.

## Acceptance Criteria

1. Equivalent evidence pointers are deduplicated consistently across reruns.
2. Evidence projection order is deterministic for unchanged inputs.
3. When subsection/offset data exists, projected pointers prefer finer-grained locators over file-level pointers.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Deterministic and deduplicated evidence projection behavior with precision preference logic.
- Regression evidence showing stable projection outputs and improved locator granularity.
