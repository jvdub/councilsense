# Additive Reader API Contract for Planned/Outcomes/Mismatch Blocks

**Task ID:** TASK-ST-027-01  
**Story:** ST-027  
**Bucket:** backend  
**Requirement Links:** ST-027 Acceptance Criteria #1, #2, #3, AGENDA_PLAN §3 Target architecture (API), AGENDA_PLAN §4 Data model and contract changes (v1-first)

## Objective

Define the additive reader API contract for `planned`, `outcomes`, and `planned_outcome_mismatches` blocks, including safe-omit behavior for optional evidence v2 fields.

## Scope

- Define field-level schema and nullability for additive planned/outcomes/mismatch blocks.
- Define compatibility behavior when additive fields are disabled or unavailable.
- Define omission semantics for unavailable evidence v2 references.
- Out of scope: serializer implementation and runtime performance checks.

## Inputs / Dependencies

- ST-006 reader API baseline list/detail semantics.
- ST-022 agenda plan v1 contract schema constraints.
- ST-026 evidence v2 additive projection baseline.

## Implementation Notes

- Preserve baseline meeting list/detail contract behavior as default.
- Keep additive fields optional and non-breaking for existing consumers.
- Use explicit schema examples for flag-off and flag-on payloads.

## Acceptance Criteria

1. Additive field contract is documented for `planned`, `outcomes`, and `planned_outcome_mismatches`.
2. Flag-off response semantics remain baseline-compatible by contract.
3. Evidence v2 fields are defined as additive and safely omittable when unavailable.
4. Contract examples cover both additive-enabled and additive-disabled payloads.

## Validation

- Review schema examples against existing API fixtures for baseline parity.
- Validate omission/nullability behavior for evidence v2 unavailable scenarios.
- Confirm additive blocks do not introduce required fields for existing clients.

## Deliverables

- Additive reader API contract specification and examples.
- Flag-off vs flag-on field presence matrix.
- Evidence v2 omission safety rules.
