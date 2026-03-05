# Scorecard Schema, Writer, and Parity Dimension Scoring

**Task ID:** TASK-ST-017-03  
**Story:** ST-017  
**Bucket:** backend  
**Requirement Links:** GAP_PLAN §Fixture + Scorecard, GAP_PLAN §Parity Targets, ST-017 Acceptance Criteria #2 and #3

## Objective
Produce a deterministic fixture scorecard artifact (JSON or Markdown) that reports all parity dimensions using frozen rubric thresholds.

## Scope
- Define scorecard schema fields for fixture identity, per-dimension scores, threshold outcomes, and run metadata.
- Implement scorecard writer for fixture runs.
- Score all required parity dimensions for each fixture.
- Out of scope: historical baseline storage policy and rerun-variance gate checks.

## Inputs / Dependencies
- TASK-ST-017-01 fixture manifest and deterministic loader behavior.
- TASK-ST-017-02 threshold constants and assertion helpers.

## Implementation Notes
- Keep schema versioned and additive for future parity dimensions.
- Include explicit pass/fail outcome per dimension, not only aggregate score.
- Ensure output ordering is deterministic for diff-friendly comparisons.

## Acceptance Criteria
1. Scorecard artifact is generated for fixture runs in a stable format.
2. Artifact includes all parity dimensions from GAP_PLAN parity targets.
3. Threshold outcomes are derived from frozen constants, not inline literals.
4. Repeated run on unchanged inputs yields byte-stable or predictably ordered artifacts.

## Validation
- Run fixture scorecard generation tests for all required dimensions.
- Compare two unchanged-run outputs to confirm deterministic artifact structure.

## Deliverables
- Scorecard schema definition and writer implementation notes.
- Fixture scorecard artifact samples for required meetings.
- Tests proving deterministic, dimension-complete scorecard generation.
