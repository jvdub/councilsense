# Quality Gate and Append-Only Publish Path

**Task ID:** TASK-ST-005-04  
**Story:** ST-005  
**Bucket:** backend  
**Requirement Links:** MVP §4.3(2-4), FR-7(3), NFR-4, NFR-7

## Objective
Implement publish decisioning that labels output as `processed` or `limited_confidence`, and enforce append-only provenance behavior after publish.

## Scope (+ Out of scope)
- Add quality-gate evaluator using evidence completeness/strength signals.
- Set publish state to `limited_confidence` when evidence is weak/absent.
- Enforce append-only writes for published summary/evidence/provenance records.
- Out of scope: reader API shape changes.

## Inputs / Dependencies
- TASK-ST-005-02, TASK-ST-005-03.
- Existing provenance persistence conventions.

## Implementation Notes
- Keep gating thresholds configurable but conservative.
- Prevent post-publish mutation by service-layer and persistence guardrails.
- Emit clear gating reason codes for operational debugging.

## Acceptance Criteria
1. Weak/absent evidence routes meeting output to `limited_confidence`.
2. Sufficient evidence routes output to `processed`.
3. Published provenance records are immutable append-only.

## Validation
- Run integration tests for both confidence branches.
- Run mutation-attempt test proving append-only protection.

## Deliverables
- Quality-gate evaluator and publish decision logic.
- Immutability safeguards and tests.
