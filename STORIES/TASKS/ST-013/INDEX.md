# ST-013 Task Index — Governance, Retention, Export, Deletion

- Story: [ST-013 — Governance: Retention, Export, and Deletion Workflows](../../ST-013-governance-retention-export-and-deletion-workflows.md)
- Requirement Links: NFR-3, NFR-7, Requirements §7 (pilot launch policy readiness)

## Ordered Checklist

- [x] [TASK-ST-013-01](TASK-ST-013-01-policy-and-sla-discovery.md) — Governance Policy Baseline and SLA Discovery
- [ ] [TASK-ST-013-02](TASK-ST-013-02-governance-request-data-model.md) — Governance Request Data Model and Lifecycle
- [ ] [TASK-ST-013-03](TASK-ST-013-03-export-workflow-and-artifacts.md) — User Export Workflow and Artifact Generation
- [ ] [TASK-ST-013-04](TASK-ST-013-04-deletion-anonymization-processing.md) — Deletion and Anonymization Processing Workflow
- [ ] [TASK-ST-013-05](TASK-ST-013-05-self-service-ui-policy-links-and-compliance-validation.md) — Self-Service Governance UI and Compliance Validation

## Dependency Chain

- TASK-ST-013-01 -> TASK-ST-013-02
- TASK-ST-013-02 -> TASK-ST-013-03
- TASK-ST-013-02 -> TASK-ST-013-04
- TASK-ST-013-03 -> TASK-ST-013-05
- TASK-ST-013-04 -> TASK-ST-013-05

## Notes

- TASK-ST-013-01 is a required discovery step because retention/deletion SLAs and policy text are legal/policy constrained.
- Tasks 03 and 04 are independently completable after task 02.
- Task 05 finalizes user-facing entry points and end-to-end validation.

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
