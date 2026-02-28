# ST-010 Task Index — Source Health + Manual Review Baseline

- Story: [ST-010 — Source Health + Manual Review Baseline](../../ST-010-source-health-and-manual-review-baseline.md)
- Requirement Links: FR-7, NFR-4, Phase 1 baseline (§9)

## Ordered Checklist

- [x] [TASK-ST-010-01](TASK-ST-010-01-health-and-confidence-policy.md) — Health and Confidence Policy
- [ ] [TASK-ST-010-02](TASK-ST-010-02-source-health-persistence.md) — Source Health Persistence
- [ ] [TASK-ST-010-03](TASK-ST-010-03-processing-version-provenance.md) — Processing Version Provenance
- [ ] [TASK-ST-010-04](TASK-ST-010-04-manual-review-state-and-reader-flag.md) — Manual Review State and Reader Flag
- [ ] [TASK-ST-010-05](TASK-ST-010-05-operator-view-and-transition-tests.md) — Operator View and Transition Tests

## Dependency Chain

- TASK-ST-010-01 -> TASK-ST-010-02
- TASK-ST-010-01 -> TASK-ST-010-04
- TASK-ST-010-02 -> TASK-ST-010-05
- TASK-ST-010-03 -> TASK-ST-010-05
- TASK-ST-010-04 -> TASK-ST-010-05

## Notes

- Keep source-level failures isolated so one city/source issue does not halt global processing.
- Persist enough run metadata for reproducibility audits.
- Manual-review routing must be deterministic and testable.

## Validation Commands

- `pytest -q`
