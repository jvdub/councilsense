# Meeting Detail evidence_references Contract Decision

**Task ID:** TASK-ST-018-01  
**Story:** ST-018  
**Bucket:** docs  
**Requirement Links:** GAP_PLAN §Gate A, FR-6, ST-018 Acceptance Criteria #2 and #3

## Objective
Define the explicit additive API contract for `evidence_references`, including behavior when evidence is absent or insufficient.

## Scope
- Decide and document whether no-evidence behavior is `[]` or field omission based on established API pattern.
- Define response-shape invariants for additive-only change requirements.
- Record fixture examples for evidence-present and evidence-sparse payloads.
- Out of scope: implementing payload shaping logic in code.

## Inputs / Dependencies
- ST-006 meeting reader API detail contract.
- Existing API response conventions for optional/additive fields.

## Implementation Notes
- Contract decision must be unambiguous so tests can enforce one behavior.
- Keep field naming, type semantics, and pointer format explicit.
- Document backward compatibility expectations for legacy consumers.

## Acceptance Criteria
1. Contract doc states exact `evidence_references` behavior for evidence-present and evidence-sparse cases.
2. Additive-only guarantee is explicitly described with no legacy field mutations.
3. Example payloads are included for both contract scenarios.
4. Contract decision is referenced by downstream test tasks.

## Validation
- Review contract doc against ST-006 response conventions.
- Verify no ambiguity remains for empty vs omitted semantics.

## Deliverables
- Contract decision document/section for `evidence_references`.
- Evidence-present and evidence-sparse payload examples.
- Traceability notes mapping decision to ST-018 acceptance criteria.
