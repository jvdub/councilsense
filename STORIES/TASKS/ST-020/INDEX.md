# ST-020 Task Index — Specificity and Evidence Locator Precision Hardening

- Story: [ST-020 — Phase 1.5: Specificity + Evidence Locator Precision Hardening](../../ST-020-phase-1-5-specificity-and-evidence-locator-precision-hardening.md)
- Requirement Links: FR-4, GAP_PLAN §Phase 3, GAP_PLAN §Parity Targets (Specificity, Grounding, Evidence precision), GAP_PLAN §Gate B

## Ordered Checklist

- [x] [TASK-ST-020-01](TASK-ST-020-01-specificity-anchor-baseline-and-fixture-gap-matrix.md) — Specificity Anchor Baseline and Fixture Gap Matrix
- [x] [TASK-ST-020-02](TASK-ST-020-02-quantitative-and-entity-anchor-harvesting.md) — Quantitative and Entity Anchor Harvesting
- [x] [TASK-ST-020-03](TASK-ST-020-03-anchor-carry-through-enforcement-in-summary-decisions-actions.md) — Anchor Carry-Through Enforcement in Summary/Decisions/Actions
- [x] [TASK-ST-020-04](TASK-ST-020-04-deterministic-evidence-projection-dedupe-and-locator-preference.md) — Deterministic Evidence Projection, Dedupe, and Locator Preference
- [x] [TASK-ST-020-05](TASK-ST-020-05-specificity-and-evidence-precision-gate-b-verification.md) — Specificity and Evidence Precision Gate B Verification

## Dependency Chain

- TASK-ST-020-01 -> TASK-ST-020-02
- TASK-ST-020-02 -> TASK-ST-020-03
- TASK-ST-020-02 -> TASK-ST-020-04
- TASK-ST-020-03 -> TASK-ST-020-05
- TASK-ST-020-04 -> TASK-ST-020-05
- TASK-ST-019-05 -> TASK-ST-020-05

## Notes

- Task 01 establishes fixture-level specificity and locator precision baselines used as the hardening target.
- Tasks 02–04 focus on additive behavior: preserve existing reliability while improving anchor retention and evidence precision.
- Task 05 validates parity thresholds and confirms no degradation to grounding coverage.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`
