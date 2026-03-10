# ST-038 Task Index — Source Catalog: On-Demand Processing Admission Control and Meeting-Level Dedupe

- Story: [ST-038 — Source Catalog: On-Demand Processing Admission Control and Meeting-Level Dedupe](../../ST-038-source-catalog-on-demand-processing-admission-control-and-meeting-level-dedupe.md)
- Requirement Links: FR-3, FR-4, FR-7, NFR-1, NFR-4

## Ordered Checklist

- [ ] [TASK-ST-038-01](TASK-ST-038-01-active-work-dedupe-key-and-meeting-level-work-identity.md) — Active-Work Dedupe Key and Meeting-Level Work Identity
- [ ] [TASK-ST-038-02](TASK-ST-038-02-admission-control-per-user-limits-and-duplicate-click-suppression.md) — Admission Control: Per-User Limits and Duplicate-Click Suppression
- [ ] [TASK-ST-038-03](TASK-ST-038-03-on-demand-work-lifecycle-integration-with-existing-pipeline-and-retry-state.md) — On-Demand Work Lifecycle Integration with Existing Pipeline and Retry State
- [ ] [TASK-ST-038-04](TASK-ST-038-04-terminal-state-request-handling-and-safe-retry-re-openings.md) — Terminal-State Request Handling and Safe Retry Re-Openings
- [ ] [TASK-ST-038-05](TASK-ST-038-05-integration-tests-for-dedupe-limits-and-idempotent-retry-behavior.md) — Integration Tests for Dedupe, Limits, and Idempotent Retry Behavior

## Dependency Chain

- TASK-ST-038-01 -> TASK-ST-038-02
- TASK-ST-037-01 -> TASK-ST-038-02
- TASK-ST-038-01 -> TASK-ST-038-03
- TASK-ST-037-03 -> TASK-ST-038-03
- TASK-ST-029-01 -> TASK-ST-038-03
- TASK-ST-038-03 -> TASK-ST-038-04
- TASK-ST-029-04 -> TASK-ST-038-04
- TASK-ST-038-02 -> TASK-ST-038-05
- TASK-ST-038-04 -> TASK-ST-038-05

## Notes

- Enforce one active job per meeting, with stable source identity as the dedupe key.
- Keep per-user limits secondary to meeting-level dedupe so identical requests converge on the same work item.
- Reuse the existing pipeline lifecycle and replay patterns rather than introducing a parallel queue model.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api pytest -q`
