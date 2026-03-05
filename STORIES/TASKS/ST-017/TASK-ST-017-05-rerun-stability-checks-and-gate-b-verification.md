# Rerun Stability Checks and Gate B Verification

**Task ID:** TASK-ST-017-05  
**Story:** ST-017  
**Bucket:** tests  
**Requirement Links:** GAP_PLAN §Gate B, GAP_PLAN §Parity Targets, ST-017 Acceptance Criteria #4 and #5

## Objective
Enforce rerun stability expectations by comparing repeated fixture scorecards against frozen rubric thresholds and baseline artifacts.

## Scope
- Add repeated-run checks on unchanged fixture inputs.
- Validate pass/fail stability and bounded score variance across reruns.
- Produce Gate B verification summary for rubric freeze readiness.
- Out of scope: introducing new scoring dimensions beyond ST-017 parity scope.

## Inputs / Dependencies
- TASK-ST-017-02 threshold constants and assertion helpers.
- TASK-ST-017-04 baseline artifacts and capture metadata.

## Implementation Notes
- Define explicit variance bounds per parity dimension in test policy.
- Treat unstable pass/fail flip on unchanged inputs as a hard failure.
- Include per-dimension drift diagnostics to speed triage.

## Acceptance Criteria
1. Two consecutive unchanged reruns show stable pass/fail outcomes per fixture/dimension.
2. Score deltas remain within documented variance bounds.
3. Gate B verification output summarizes stability status and any failures.
4. Verification can run in local and CI pathways without runtime feature changes.

## Validation
- Run rerun-stability suite over full fixture cohort.
- Run Gate B verification command path and inspect summary output.
- Confirm failure diagnostics identify fixture and dimension when bounds are exceeded.

## Deliverables
- Rerun stability test coverage and variance-bound checks.
- Gate B verification report artifact.
- Troubleshooting notes for instability triage.
