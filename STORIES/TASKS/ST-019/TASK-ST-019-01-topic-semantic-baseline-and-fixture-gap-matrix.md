# Topic Semantic Baseline and Fixture Gap Matrix

**Task ID:** TASK-ST-019-01  
**Story:** ST-019  
**Bucket:** tests  
**Requirement Links:** FR-4, GAP_PLAN §Parity Targets (Topic quality), GAP_PLAN §Gate B

## Objective

Produce a reproducible baseline that classifies current topic-quality failures per fixture so semantic hardening work can be measured.

## Scope

- Define fixture-level checks for generic-only topic labels, missing civic concept phrasing, and missing topic evidence mappings.
- Capture baseline metrics and failure examples in a story-local artifact for regression comparison.
- Out of scope: changing production topic extraction behavior.

## Inputs / Dependencies

- ST-019 story definition and acceptance criteria.
- Existing fixture scorecard outputs from ST-017 and additive contract constraints from ST-018.

## Implementation Notes

- Reuse existing fixture and scorecard execution paths; do not introduce a parallel evaluation framework.
- Keep failure categories deterministic so reruns produce the same classification for unchanged inputs.
- Persist baseline artifacts in story-task documentation paths or existing quality artifact paths already used by the repository.

## Acceptance Criteria

1. Baseline run produces a fixture matrix that labels each failure by semantic category (generic token, weak concept phrase, or missing topic evidence mapping).
2. The baseline includes counts and representative examples for each category.
3. A follow-up rerun with no code changes reproduces the same category counts.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Documented baseline matrix and category definitions referenced by subsequent ST-019 tasks.
- Updated story evidence notes indicating initial semantic gap magnitude.
