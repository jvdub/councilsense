# Additive evidence_references Projection and Serialization

**Task ID:** TASK-ST-018-02  
**Story:** ST-018  
**Bucket:** backend  
**Requirement Links:** MVP §4.5(1-2), FR-6, ST-018 Acceptance Criteria #1 and #2

## Objective
Implement additive projection and deterministic serialization rules for `evidence_references` in meeting detail responses.

## Scope
- Add meeting-detail projection path for `evidence_references` without changing existing fields.
- Define deterministic ordering and formatting for serialized evidence pointers.
- Preserve existing reader API response semantics.
- Out of scope: contract compatibility regression suite and release documentation.

## Inputs / Dependencies
- TASK-ST-018-01 contract decision for empty/omitted behavior.
- Existing meeting-detail payload shaping pipeline from ST-006.

## Implementation Notes
- Use additive response shaping only; do not rename or repurpose legacy fields.
- Keep serialization deterministic to prevent flaky contract assertions.
- Enforce schema-safe defaults for absent evidence according to Task 01 decision.

## Acceptance Criteria
1. Meeting detail payload includes `evidence_references` when evidence exists.
2. Evidence pointer serialization is deterministic across unchanged runs.
3. Legacy fields remain unchanged in name, type, and semantics.
4. No breaking schema deltas are introduced for current consumers.

## Validation
- Run meeting detail serialization tests for deterministic output.
- Execute reader API response snapshots comparing before/after legacy fields.

## Deliverables
- Additive payload projection updates for `evidence_references`.
- Deterministic serialization rules and tests.
- Compatibility notes confirming additive-only delta.
