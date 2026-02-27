# ST-015 Task Index — Quality Operations and ECR Audits

- Story: [ST-015 — Phase 1.5: Quality Operations + ECR Audits](../../ST-015-phase-1-5-quality-operations-and-ecr-audits.md)
- Requirement Links: FR-4, NFR-4, Success Metrics §8 (ECR), Phase 1.5 §9

## Ordered Checklist

- [ ] [TASK-ST-015-01](TASK-ST-015-01-weekly-audit-sampling-spec-and-schedule.md) — Weekly Audit Sampling Spec and Schedule
- [ ] [TASK-ST-015-02](TASK-ST-015-02-ecr-audit-job-and-report-artifact.md) — ECR Audit Job and Weekly Report Artifact
- [ ] [TASK-ST-015-03](TASK-ST-015-03-reviewer-queue-and-outcome-capture.md) — Reviewer Queue and Outcome Capture for Low-Confidence Outputs
- [ ] [TASK-ST-015-04](TASK-ST-015-04-confidence-calibration-policy-controls.md) — Confidence Calibration Policy Controls
- [ ] [TASK-ST-015-05](TASK-ST-015-05-quality-ops-dashboard-and-ecr-target-validation.md) — Quality Operations Dashboard and ECR Target Validation

## Dependency Chain

- TASK-ST-015-01 -> TASK-ST-015-02
- TASK-ST-015-02 -> TASK-ST-015-03
- TASK-ST-015-03 -> TASK-ST-015-04
- TASK-ST-015-02 -> TASK-ST-015-05
- TASK-ST-015-03 -> TASK-ST-015-05
- TASK-ST-015-04 -> TASK-ST-015-05

## Notes

- Hardening outputs are measurable: weekly ECR, low-confidence labeling rate, reviewer closure rate, threshold change impact.
- Task 05 is release evidence for ECR target tracking (>= 85% on audited sample).

## Validation Commands

- `pytest -q`
