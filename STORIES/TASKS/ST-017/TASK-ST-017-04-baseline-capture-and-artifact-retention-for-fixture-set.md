# Baseline Capture and Artifact Retention for Fixture Set

**Task ID:** TASK-ST-017-04  
**Story:** ST-017  
**Bucket:** ops  
**Requirement Links:** GAP_PLAN §Phase 0, GAP_PLAN §Fixture + Scorecard, ST-017 Acceptance Criteria #2 and #4

## Objective

Capture and retain pre-change baseline scorecards for Eagle Mountain and comparison fixtures to support later parity delta analysis.

## Scope

- Define baseline capture workflow for initial fixture runs.
- Store baseline artifacts with run metadata and fixture fingerprints.
- Document retention location and naming conventions for baseline comparisons.
- Out of scope: enforcing pass/fail gates on rerun variance.

## Inputs / Dependencies

- TASK-ST-017-03 scorecard schema and writer outputs.
- Existing artifact retention conventions for local/CI quality runs.

## Implementation Notes

- Baseline snapshot must include exact fixture manifest reference and rubric version.
- Preserve immutable baseline records; later runs should append new snapshots.
- Record who/when/where baseline was captured for auditability.

## Acceptance Criteria

1. Baseline scorecards exist for Eagle Mountain and both comparison meetings.
2. Baseline artifacts include fixture identity, rubric version, and run timestamp metadata.
3. Artifact naming and location allow deterministic retrieval for delta checks.
4. Baseline capture workflow is documented for local and CI execution.

## Validation

- Execute baseline capture workflow and verify artifacts for all required fixtures.
- Verify metadata completeness and retrieval path with a dry-run comparison command.

## Deliverables

- Baseline scorecard artifact set for required fixture cohort.
- Retention and naming convention documentation.
- Validation notes demonstrating retrievable baseline snapshots.
