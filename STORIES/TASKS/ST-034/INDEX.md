# ST-034 Task Index — Resident Relevance Meeting Detail Impact Cards and Scan View

- Story: [ST-034 — Resident Relevance: Meeting Detail Impact Cards and Scan View](../../ST-034-frontend-meeting-detail-resident-impact-cards-and-scan-view.md)
- Requirement Links: FR-4, REQUIREMENTS §12.3 Web App, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome, REQUIREMENTS §14(3,10)

## Ordered Checklist

- [x] [TASK-ST-034-01](TASK-ST-034-01-feature-flag-contract-and-scan-card-component-model.md) — Feature Flag Contract and Scan-Card Component Model
- [x] [TASK-ST-034-02](TASK-ST-034-02-resident-impact-cards-rendering-and-structured-data-binding.md) — Resident Impact Cards Rendering and Structured Data Binding
- [x] [TASK-ST-034-03](TASK-ST-034-03-navigation-affordances-and-empty-state-behavior.md) — Navigation Affordances and Empty-State Behavior
- [x] [TASK-ST-034-04](TASK-ST-034-04-frontend-tests-accessibility-and-baseline-parity-hardening.md) — Frontend Tests, Accessibility, and Baseline Parity Hardening

## Dependency Chain

- TASK-ST-034-01 -> TASK-ST-034-02
- TASK-ST-034-01 -> TASK-ST-034-03
- TASK-ST-034-02 -> TASK-ST-034-04
- TASK-ST-034-03 -> TASK-ST-034-04
- TASK-ST-033-03 -> TASK-ST-034-02

## Notes

- Keep the resident scan layer additive to the current meeting detail surface; no separate route.
- Preserve baseline detail rendering when flags are off or structured relevance fields are absent.
- Favor fast scanning and evidence access over replacing the underlying meeting detail sections.

## Validation Commands

- `npm --prefix frontend run test`
- `npm --prefix frontend run build`