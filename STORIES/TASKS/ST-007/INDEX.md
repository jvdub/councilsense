# ST-007 Task Index — Frontend Meetings List + Detail Experience

- Story: [ST-007 — Frontend Meetings List + Detail Experience](../../ST-007-frontend-meetings-list-and-detail-experience.md)
- Requirement Links: MVP §4.5(1-3), FR-4, NFR-2

## Ordered Checklist

- [x] [TASK-ST-007-01](TASK-ST-007-01.md) — Meetings Reader Client and Models
- [ ] [TASK-ST-007-02](TASK-ST-007-02.md) — Meetings List Page
- [ ] [TASK-ST-007-03](TASK-ST-007-03.md) — Meeting Detail Page with Evidence and Confidence
- [ ] [TASK-ST-007-04](TASK-ST-007-04.md) — Notification Deep-Link Routing to Meeting Detail
- [ ] [TASK-ST-007-05](TASK-ST-007-05.md) — ST-007 Reader UX Smoke Coverage

## Dependency Chain

- TASK-ST-007-01 -> TASK-ST-007-02
- TASK-ST-007-01 -> TASK-ST-007-03
- TASK-ST-007-03 -> TASK-ST-007-04
- TASK-ST-007-02 -> TASK-ST-007-05
- TASK-ST-007-03 -> TASK-ST-007-05
- TASK-ST-007-04 -> TASK-ST-007-05

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
