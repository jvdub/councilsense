# ST-039 Task Index — Source Catalog: Frontend Meeting Explorer and On-Demand Processing UX

- Story: [ST-039 — Source Catalog: Frontend Meeting Explorer and On-Demand Processing UX](../../ST-039-source-catalog-frontend-meeting-explorer-and-on-demand-processing-ux.md)
- Requirement Links: FR-4, FR-6, NFR-2

## Ordered Checklist

- [ ] [TASK-ST-039-01](TASK-ST-039-01-meetings-page-pagination-and-api-contract.md) — Meetings Page Pagination and API Contract
- [ ] [TASK-ST-039-02](TASK-ST-039-02-tile-state-rendering-and-variants.md) — Tile State Rendering and Variants
- [ ] [TASK-ST-039-03](TASK-ST-039-03-request-action-and-user-messaging.md) — Request Action and User Messaging
- [ ] [TASK-ST-039-04](TASK-ST-039-04-deep-linking-and-navigation-preservation.md) — Deep-Linking and Navigation Preservation
- [ ] [TASK-ST-039-05](TASK-ST-039-05-page-tests-accessibility-and-hardening.md) — Page Tests, Accessibility, and Hardening

## Dependency Chain

- TASK-ST-039-01 -> TASK-ST-039-02
- TASK-ST-039-01 -> TASK-ST-039-04
- TASK-ST-039-02 -> TASK-ST-039-03
- TASK-ST-039-02 -> TASK-ST-039-05
- TASK-ST-039-03 -> TASK-ST-039-05
- TASK-ST-039-04 -> TASK-ST-039-05
- TASK-ST-037-01 -> TASK-ST-039-01
- TASK-ST-038-02 -> TASK-ST-039-03

## Notes

- Keep the meeting explorer additive to the existing meeting detail flow rather than replacing it.
- Preserve a flag-off path that can fall back to the current processed-meetings list behavior if rollout is staged.
- Surface queue outcomes in resident-friendly terms without exposing backend queue internals.

## Validation Commands

- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
