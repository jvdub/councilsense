# ST-008 Task Index — Notification Preferences + Push Subscriptions UI

- Story: [ST-008 — Notification Preferences + Push Subscriptions UI](../../ST-008-notification-preferences-and-push-subscriptions-ui.md)
- Requirement Links: MVP §4.4(2-5), FR-2, FR-5(4-5), NFR-3

## Ordered Checklist

- [x] [TASK-ST-008-01](TASK-ST-008-01.md) — Push Capability and Contract Discovery
- [x] [TASK-ST-008-02](TASK-ST-008-02.md) — Notification Settings Toggles and Persistence
- [x] [TASK-ST-008-03](TASK-ST-008-03.md) — Push Subscribe/Unsubscribe UX
- [x] [TASK-ST-008-04](TASK-ST-008-04.md) — Subscription API Wiring and Recovery State Mapping
- [ ] [TASK-ST-008-05](TASK-ST-008-05.md) — ST-008 End-to-End Settings and Push Flow Tests

## Dependency Chain

- TASK-ST-008-01 -> TASK-ST-008-03
- TASK-ST-008-01 -> TASK-ST-008-04
- TASK-ST-008-02 -> TASK-ST-008-03
- TASK-ST-008-03 -> TASK-ST-008-04
- TASK-ST-008-02 -> TASK-ST-008-05
- TASK-ST-008-03 -> TASK-ST-008-05
- TASK-ST-008-04 -> TASK-ST-008-05

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
