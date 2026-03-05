# Quantitative and Entity Anchor Harvesting

**Task ID:** TASK-ST-020-02  
**Story:** ST-020  
**Bucket:** backend  
**Requirement Links:** FR-4, GAP_PLAN §Phase 3, GAP_PLAN §Parity Targets (Specificity)

## Objective

Implement harvesting of quantitative and entity-like anchors from parsed meeting content for downstream carry-through and evidence linking.

## Scope

- Extract specificity anchors including units, acres, dates, counts, and named entities from parsed artifacts.
- Normalize anchor representation so downstream assembly can use consistent anchor objects.
- Out of scope: enforcement of anchor presence in final summary/decisions/actions (handled in TASK-ST-020-03).

## Inputs / Dependencies

- TASK-ST-020-01 baseline matrix and anchor gap categories.
- Existing parsed meeting content structures and summarization pipeline contracts.

## Implementation Notes

- Reuse parser outputs already available in the pipeline before adding new extraction heuristics.
- Keep anchor extraction deterministic and traceable back to source spans where possible.
- Avoid broad NLP redesign; focus on concrete anchor classes in the story scope.

## Acceptance Criteria

1. Anchor harvesting captures all scoped anchor classes on fixtures that contain them.
2. Harvested anchors are represented in a stable structure consumable by output assembly.
3. Reruns on unchanged input produce consistent harvested anchor sets.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Anchor harvesting implementation covering quantitative and entity-like specificity signals.
- Test evidence demonstrating deterministic extraction for baseline fixtures.
