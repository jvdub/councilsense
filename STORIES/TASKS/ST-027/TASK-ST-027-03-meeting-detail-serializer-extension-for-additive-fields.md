# Meeting Detail Serializer Extension for Additive Fields

**Task ID:** TASK-ST-027-03  
**Story:** ST-027  
**Bucket:** backend  
**Requirement Links:** ST-027 Acceptance Criteria #2, #3, AGENDA_PLAN §3 Target architecture (API), AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches

## Objective

Extend meeting detail serialization to emit additive `planned`, `outcomes`, and `planned_outcome_mismatches` blocks with safe evidence v2 inclusion.

## Scope

- Implement additive serializer fields for planned/outcomes/mismatch blocks.
- Wire evidence v2 inclusion into additive blocks when available.
- Ensure omission behavior is safe and deterministic when additive inputs are missing.
- Out of scope: frontend rendering behavior and deep-link UX enhancements.

## Inputs / Dependencies

- TASK-ST-027-01 contract semantics for additive blocks.
- TASK-ST-027-02 feature controls and parity guard behavior.
- TASK-ST-026-03 additive `evidence_references_v2` projection support.

## Implementation Notes

- Preserve existing meeting detail/list serializer semantics outside additive fields.
- Keep additive structures stable under partial-source meetings.
- Ensure mismatch records are emitted only when evidence-backed input exists.

## Acceptance Criteria

1. Flag-on responses include `planned`, `outcomes`, and `planned_outcome_mismatches` blocks.
2. Evidence v2 fields are included when available and safely omitted when unavailable.
3. Baseline fields and semantics remain unchanged for existing clients.
4. Serializer output is deterministic for identical inputs.

## Validation

- Execute serializer tests for full-source, partial-source, and no-mismatch scenarios.
- Validate flag-off outputs remain baseline-equivalent.
- Verify evidence v2 inclusion/omission behavior across mixed availability fixtures.

## Deliverables

- Meeting detail serializer additive field implementation.
- Deterministic output examples for flag-on and flag-off states.
- Evidence inclusion/omission behavior notes.
