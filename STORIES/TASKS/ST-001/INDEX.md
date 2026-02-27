# ST-001 Task Index — Managed Auth + Home City Onboarding

- Story: [ST-001 — Managed Auth + Home City Onboarding](../../ST-001-auth-google-and-home-city-onboarding.md)
- Requirement Links: MVP §4.1, FR-1, FR-2, FR-6, NFR-3, NFR-5

## Ordered Checklist

- [x] [TASK-ST-001-01](TASK-ST-001-01-auth-google-config.md) — Configure Google managed auth and local callbacks
- [x] [TASK-ST-001-02](TASK-ST-001-02-backend-auth-middleware.md) — Add backend auth and session validation middleware
- [x] [TASK-ST-001-03](TASK-ST-001-03-user-bootstrap-onboarding-guard.md) — Implement user bootstrap and onboarding guard
- [ ] [TASK-ST-001-04](TASK-ST-001-04-frontend-onboarding-city-selection.md) — Build onboarding city selection flow
- [ ] [TASK-ST-001-05](TASK-ST-001-05-auth-onboarding-integration-tests.md) — Add auth and onboarding integration coverage

## Dependency Chain

- TASK-ST-001-01 -> TASK-ST-001-02
- TASK-ST-001-02 -> TASK-ST-001-03
- TASK-ST-001-03 -> TASK-ST-001-04
- TASK-ST-001-03 -> TASK-ST-001-05
- TASK-ST-001-04 -> TASK-ST-001-05

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
