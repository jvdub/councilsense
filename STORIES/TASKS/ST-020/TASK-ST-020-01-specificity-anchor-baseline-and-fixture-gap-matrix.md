# Specificity Anchor Baseline and Fixture Gap Matrix

**Task ID:** TASK-ST-020-01  
**Story:** ST-020  
**Bucket:** tests  
**Requirement Links:** FR-4, GAP_PLAN §Parity Targets (Specificity, Grounding, Evidence precision), GAP_PLAN §Gate B

## Objective

Build a reproducible baseline that identifies where quantitative anchors and precise evidence locators are currently missing in fixture outputs.

## Scope

- Define baseline checks for anchor presence (units, acres, dates, counts, named entities) in summary or key decisions/actions.
- Measure evidence pointer granularity (file-level vs subsection/offset-level when available).
- Record deterministic projection/dedupe consistency across reruns.
- Out of scope: changing extraction or projection behavior.

## Inputs / Dependencies

- ST-020 acceptance criteria and fixture set used by scorecard evaluation.
- Existing grounding and additive evidence contracts from ST-018.

## Implementation Notes

- Keep baseline categories explicit so each missing-anchor or low-precision case is actionable.
- Use stable fixture identifiers in all baseline artifacts.
- Store baseline evidence in task/story documentation or established evaluation artifact paths.

## Acceptance Criteria

1. Baseline matrix reports missing-anchor cases, grounding status, and locator precision class per fixture.
2. Baseline includes deterministic rerun comparison for evidence projection ordering and dedupe outcomes.
3. Baseline artifacts are sufficient to compare improvements in subsequent ST-020 tasks.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Fixture-level specificity and locator precision baseline matrix.
- Documented baseline metrics used as acceptance evidence for later ST-020 tasks.
