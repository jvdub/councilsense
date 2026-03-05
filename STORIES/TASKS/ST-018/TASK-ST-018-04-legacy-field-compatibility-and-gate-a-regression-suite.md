# Legacy Field Compatibility and Gate A Regression Suite

**Task ID:** TASK-ST-018-04  
**Story:** ST-018  
**Bucket:** tests  
**Requirement Links:** GAP_PLAN §Gate A, NFR-2, ST-018 Acceptance Criteria #2 and #5

## Objective
Prove additive-only API evolution by running regression checks that compare legacy field behavior before and after `evidence_references` addition.

## Scope
- Add regression assertions for unchanged legacy meeting-detail fields.
- Run Gate A contract-safety checks in local and CI paths.
- Report additive delta boundaries for API consumers.
- Out of scope: introducing new fields beyond `evidence_references`.

## Inputs / Dependencies
- TASK-ST-018-02 additive projection implementation.
- TASK-ST-018-03 fixture-backed contract tests.

## Implementation Notes
- Use snapshot or schema-diff tooling that ignores approved additive field.
- Treat any legacy field semantic drift as regression failure.
- Include local and CI command parity for Gate A checks.

## Acceptance Criteria
1. Regression suite confirms no changes to existing fields and semantics.
2. Gate A contract-safety checks pass in local execution path.
3. CI-oriented contract path is documented and runnable.
4. Any non-additive API delta is surfaced as a blocking failure.

## Validation
- Run local Gate A contract suite and capture pass output.
- Execute CI-equivalent contract command path in dry-run or test mode.
- Review schema diff output to confirm additive-only change.

## Deliverables
- Legacy compatibility regression test suite updates.
- Gate A contract-safety validation evidence for local and CI paths.
- Additive-delta report artifact for reviewer sign-off.
