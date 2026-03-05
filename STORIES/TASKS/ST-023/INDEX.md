# ST-023 Task Index — Meeting Bundle Planner and Source-Scoped Ingestion

- Story: [ST-023 — Agenda Plan: Meeting Bundle Planner and Source-Scoped Ingestion](../../ST-023-meeting-bundle-planner-and-source-scoped-ingestion.md)
- Requirement Links: AGENDA_PLAN §3 Target architecture, AGENDA_PLAN §5 Phase 1 — MVP multi-source ingestion and publish continuity, AGENDA_PLAN §6 Testing and validation plan

## Ordered Checklist

- [x] [TASK-ST-023-01](TASK-ST-023-01-meeting-bundle-planner-rules-and-candidate-resolution.md) — Meeting Bundle Planner Rules and Candidate Resolution
- [x] [TASK-ST-023-02](TASK-ST-023-02-source-scoped-idempotency-and-checksum-dedupe.md) — Source-Scoped Idempotency and Checksum Dedupe
- [x] [TASK-ST-023-03](TASK-ST-023-03-bundle-state-tracking-and-source-outcome-wiring.md) — Bundle State Tracking and Source Outcome Wiring
- [x] [TASK-ST-023-04](TASK-ST-023-04-deterministic-rerun-and-duplicate-prevention-tests.md) — Deterministic Rerun and Duplicate Prevention Tests
- [ ] [TASK-ST-023-05](TASK-ST-023-05-pilot-city-minutes-plus-supplemental-smoke-fixture.md) — Pilot-City Minutes Plus Supplemental Smoke Fixture

## Dependency Chain

- TASK-ST-023-01 -> TASK-ST-023-02
- TASK-ST-023-01 -> TASK-ST-023-03
- TASK-ST-023-02 -> TASK-ST-023-03
- TASK-ST-023-02 -> TASK-ST-023-04
- TASK-ST-023-03 -> TASK-ST-023-04
- TASK-ST-023-04 -> TASK-ST-023-05

## Notes

- Keep planning deterministic for same city/meeting/source inputs across reruns.
- Enforce source-scoped dedupe before publish to prevent duplicate documents/artifacts/publications.
- Validate pilot-city flow includes minutes plus at least one supplemental source artifact.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id <pilot-city-id>`
