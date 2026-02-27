# ST-003 Task Index — City Registry + Source Configuration

- Story: [ST-003 — City Registry + Source Configuration](../../ST-003-city-registry-and-source-configuration.md)
- Requirement Links: MVP §4.2, FR-2, FR-3, FR-7, NFR-5

## Ordered Checklist

- [x] [TASK-ST-003-01](TASK-ST-003-01-city-registry-schema.md) — Create city and city-source schema foundations
- [x] [TASK-ST-003-02](TASK-ST-003-02-pilot-city-source-seed.md) — Seed pilot city and initial source configuration
- [ ] [TASK-ST-003-03](TASK-ST-003-03-registry-service-layer.md) — Implement configured city/source selection service
- [ ] [TASK-ST-003-04](TASK-ST-003-04-meeting-city-linkage-enforcement.md) — Enforce mandatory city linkage in meeting writes
- [ ] [TASK-ST-003-05](TASK-ST-003-05-city-registry-eligibility-tests.md) — Add city registry and eligibility test coverage

## Dependency Chain

- TASK-ST-003-01 -> TASK-ST-003-02
- TASK-ST-003-01 -> TASK-ST-003-03
- TASK-ST-003-02 -> TASK-ST-003-03
- TASK-ST-003-03 -> TASK-ST-003-04
- TASK-ST-003-03 -> TASK-ST-003-05
- TASK-ST-003-04 -> TASK-ST-003-05

## Validation Commands

- `pytest -q`
