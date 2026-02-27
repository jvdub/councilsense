# Weekly Audit Sampling Spec and Schedule

**Task ID:** TASK-ST-015-01  
**Story:** ST-015  
**Bucket:** ops  
**Requirement Links:** Success Metrics §8 (ECR), Phase 1.5 §9

## Objective
Define reproducible weekly sampling and audit cadence used to compute ECR and drive reviewer workflows.

## Scope
- Specify sampling frame, sample size, and selection method.
- Define weekly schedule and ownership.
- Define report schema required by downstream tasks.
- Out of scope: implementing audit computation or reviewer queue logic.

## Inputs / Dependencies
- Published summary/evidence dataset definitions from ST-005.
- Operations cadence constraints.

## Implementation Notes
- Prefer deterministic/random-seeded sampling for reproducibility.
- Include minimum sample representativeness rules (city/source spread).
- Define handling for missing or malformed samples.

## Acceptance Criteria
1. Weekly sampling method is documented and reproducible.
2. Schedule and owner for audit execution are assigned.
3. Audit report schema is agreed for ECR and confidence outputs.
4. Sampling output can be regenerated for a prior audit window.

## Validation
- Dry-run sampling for one historical week.
- Re-run with same seed/window and confirm identical sample.
- Stakeholder review sign-off on sampling spec.

## Deliverables
- Sampling specification document.
- Scheduler configuration requirements.
- Audit report schema contract.
