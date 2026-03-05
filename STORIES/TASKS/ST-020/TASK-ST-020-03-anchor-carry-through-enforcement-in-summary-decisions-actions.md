# Anchor Carry-Through Enforcement in Summary/Decisions/Actions

**Task ID:** TASK-ST-020-03  
**Story:** ST-020  
**Bucket:** backend  
**Requirement Links:** FR-4, GAP_PLAN §Parity Targets (Specificity, Grounding)

## Objective

Enforce carry-through of available anchors into summary or key decisions/actions so high-value specifics are retained for readers.

## Scope

- Add assembly-time checks that retain at least one relevant anchor when source anchors exist.
- Ensure grounding coverage remains complete for key decisions/actions while anchors are propagated.
- Define fallback behavior for cases where anchor extraction returns low-confidence or conflicting candidates.
- Out of scope: evidence pointer dedupe/ranking mechanics and locator precision preference (covered in TASK-ST-020-04).

## Inputs / Dependencies

- TASK-ST-020-02 harvested anchor outputs.
- Existing summary/decision/action contract behavior and grounding checks.

## Implementation Notes

- Keep output contract backward compatible; changes should be additive in content quality, not schema changes.
- Make carry-through rules explicit and testable per fixture class.
- Prevent over-insertion of anchors that reduce readability or misstate context.

## Acceptance Criteria

1. Fixtures with available anchors include at least one anchor in summary or key decisions/actions.
2. Grounding coverage for key decisions/actions remains 100% after carry-through enforcement.
3. Carry-through behavior is stable across reruns for unchanged fixture inputs.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Anchor carry-through enforcement logic integrated into output assembly.
- Fixture validation evidence showing improved specificity retention without grounding regressions.
