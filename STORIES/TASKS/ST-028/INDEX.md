# ST-028 Task Index — Frontend Meeting Detail Planned/Outcomes and Mismatch Rendering

- Story: [ST-028 — Frontend Meeting Detail Planned/Outcomes and Mismatch Rendering](../../ST-028-frontend-meeting-detail-planned-outcomes-and-mismatch-rendering.md)
- Requirement Links: AGENDA_PLAN §2 Scope and non-goals, AGENDA_PLAN §3 Target architecture (frontend), AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches (Weeks 6–7)

## Ordered Checklist

- [ ] [TASK-ST-028-01](TASK-ST-028-01-meeting-detail-flag-contract-and-render-mode-resolution.md) — Meeting Detail Flag Contract and Render Mode Resolution
- [ ] [TASK-ST-028-02](TASK-ST-028-02-planned-and-outcomes-sections-and-data-binding.md) — Planned and Outcomes Sections and Data Binding
- [ ] [TASK-ST-028-03](TASK-ST-028-03-evidence-backed-mismatch-indicators-and-empty-states.md) — Evidence-Backed Mismatch Indicators and Empty States
- [ ] [TASK-ST-028-04](TASK-ST-028-04-additive-field-fallback-and-baseline-parity-hardening.md) — Additive-Field Fallback and Baseline Parity Hardening
- [ ] [TASK-ST-028-05](TASK-ST-028-05-frontend-tests-accessibility-and-latency-regression-checks.md) — Frontend Tests, Accessibility, and Latency Regression Checks

## Dependency Chain

- TASK-ST-028-01 -> TASK-ST-028-02
- TASK-ST-028-01 -> TASK-ST-028-03
- TASK-ST-028-02 -> TASK-ST-028-04
- TASK-ST-028-03 -> TASK-ST-028-04
- TASK-ST-028-04 -> TASK-ST-028-05

## Notes

- Keep implementation additive to the existing meeting detail route; no standalone new reader surface.
- Preserve strict flag-off baseline parity and activate planned/outcomes rendering only when additive data and flags are present.
- Enforce mismatch rendering gate: show mismatch signals only when evidence-backed metadata is available.

## Validation Commands

- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
