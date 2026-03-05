# Promotion Controller for Consecutive Green Report-Only Runs

**Task ID:** TASK-ST-030-04  
**Story:** ST-030  
**Bucket:** tests  
**Requirement Links:** ST-030 Acceptance Criteria #3, AGENDA_PLAN §5 Phase 4 — Hardening, AGENDA_PLAN §10 Decision log and open questions

## Objective
Implement promotion checks that require two consecutive green report-only runs before any enforcement expansion.

## Scope
- Define promotion eligibility algorithm over report-only diagnostics windows.
- Track consecutive-green status with reset behavior on any failure or missing diagnostic.
- Produce promotion evidence artifacts with run IDs, gates, and eligibility decision.
- Out of scope: enforcement policy hooks and rollback command sequence.

## Inputs / Dependencies
- TASK-ST-030-01 gate threshold contract.
- TASK-ST-030-02 report-only diagnostics artifacts.
- Existing rollout-control mechanisms from ST-021 promotion criteria.

## Implementation Notes
- Promotion requires two consecutive green runs for all document-aware gates.
- Missing diagnostics count as non-green and reset progression.
- Promotion artifacts must be immutable and reviewable for release approval.

## Acceptance Criteria
1. Promotion logic only allows enforcement expansion after two consecutive all-green report-only runs.
2. Any failed or missing gate result resets the consecutive-green counter.
3. Promotion artifact records run IDs, gate outcomes, and final eligibility decision.
4. Promotion output can be consumed in release readiness reviews.

## Validation
- Replay pass-pass, pass-fail-pass, and fail-pass-pass report-only sequences.
- Verify eligibility only for qualifying two-green windows.
- Confirm reproducibility of promotion artifacts across reruns.

## Deliverables
- Promotion eligibility algorithm specification.
- Consecutive-green scenario matrix and expected outcomes.
- Promotion evidence artifact template and sample output.
