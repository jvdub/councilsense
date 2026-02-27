# ST-002 Task Index — Profile Preferences + Self-Service Controls

- Story: [ST-002 — Profile Preferences + Self-Service Controls](../../ST-002-profile-preferences-and-self-service-controls.md)
- Requirement Links: MVP §4.1(4), MVP §4.4(4), FR-2, FR-5(4), FR-6, NFR-3

## Ordered Checklist

- [x] [TASK-ST-002-01](TASK-ST-002-01-profile-preference-schema-alignment.md) — Align profile preference schema fields
- [x] [TASK-ST-002-02](TASK-ST-002-02-profile-api-get-patch.md) — Implement profile read/update endpoints
- [ ] [TASK-ST-002-03](TASK-ST-002-03-self-only-authz-and-pause-rules.md) — Enforce self-only authz and pause rules
- [ ] [TASK-ST-002-04](TASK-ST-002-04-frontend-settings-preferences.md) — Build settings editor for profile preferences
- [ ] [TASK-ST-002-05](TASK-ST-002-05-profile-preferences-integration-tests.md) — Add profile preferences integration tests

## Dependency Chain

- TASK-ST-002-01 -> TASK-ST-002-02
- TASK-ST-002-02 -> TASK-ST-002-03
- TASK-ST-002-02 -> TASK-ST-002-04
- TASK-ST-002-03 -> TASK-ST-002-05
- TASK-ST-002-04 -> TASK-ST-002-05

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
