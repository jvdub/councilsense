# Specificity and Evidence Precision Gate B Verification

**Task ID:** TASK-ST-020-05  
**Story:** ST-020  
**Bucket:** ops  
**Requirement Links:** FR-4, GAP_PLAN §Gate B, GAP_PLAN §Parity Targets (Specificity, Grounding, Evidence precision)

## Objective

Verify end-to-end that specificity retention and evidence locator precision thresholds pass across fixtures without degrading publish reliability.

## Scope

- Run full fixture scorecard and capture specificity, grounding, and evidence-precision outcomes.
- Compare final results to TASK-ST-020-01 baseline and confirm measurable improvements.
- Document readiness decision, residual risks, and rollback triggers for ST-020 hardening.
- Out of scope: post-Gate-B enhancements not required by ST-020 acceptance criteria.

## Inputs / Dependencies

- TASK-ST-020-03 anchor carry-through enforcement.
- TASK-ST-020-04 deterministic projection and locator precision preferences.
- TASK-ST-019-05 topic semantic hardening verification outputs.

## Implementation Notes

- Use identical fixture cohorts and command paths across baseline and final runs for fair comparison.
- Include explicit evidence for deterministic rerun behavior in final verification notes.
- Keep verification artifacts easy to audit by release owners.

## Acceptance Criteria

1. Fixtures with quantitative/entity anchors meet carry-through expectations in summary or key decisions/actions.
2. Grounding coverage for key decisions/actions remains 100% in final verification output.
3. Evidence projection determinism and locator precision thresholds pass without introducing reliability regressions.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- ST-020 Gate B verification notes with baseline comparison and go/no-go recommendation.
- Final story-level evidence packet for specificity and locator precision hardening.
