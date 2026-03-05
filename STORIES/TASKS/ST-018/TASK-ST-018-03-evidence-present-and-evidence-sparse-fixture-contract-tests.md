# Evidence-Present and Evidence-Sparse Fixture Contract Tests

**Task ID:** TASK-ST-018-03  
**Story:** ST-018  
**Bucket:** tests  
**Requirement Links:** GAP_PLAN §Gate A, ST-018 Acceptance Criteria #1 and #3

## Objective
Create fixture-backed contract tests that enforce `evidence_references` behavior in both evidence-present and evidence-sparse scenarios.

## Scope
- Build/extend fixtures covering evidence-rich and evidence-sparse meetings.
- Assert contract behavior exactly as decided in TASK-ST-018-01.
- Verify deterministic serialization and field presence semantics.
- Out of scope: full backward-compatibility regression across all legacy fields.

## Inputs / Dependencies
- TASK-ST-018-01 contract decision and examples.
- TASK-ST-018-02 additive projection and serialization behavior.

## Implementation Notes
- Include fixture metadata that makes evidence availability explicit.
- Keep assertions focused on API contract, not summarization quality scoring.
- Fail with clear diagnostics for contract-shape mismatch.

## Acceptance Criteria
1. Evidence-present fixture asserts non-empty `evidence_references` output.
2. Evidence-sparse fixture asserts exact empty/omitted behavior from contract decision.
3. Tests confirm stable pointer formatting across reruns.
4. Contract failures identify fixture, field path, and expected behavior.

## Validation
- Run fixture-backed contract test suite for both scenarios.
- Re-run tests to verify deterministic behavior and stable pass/fail outcomes.

## Deliverables
- Fixture additions/updates for evidence-present and evidence-sparse scenarios.
- Contract test coverage for `evidence_references` behavior.
- Failure-diagnostic assertions for schema/shape mismatches.
