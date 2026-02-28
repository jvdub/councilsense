# ST-006 Task Index — Meeting Reader API (City List + Detail)

- Story: [ST-006 — Meeting Reader API (City List + Detail)](../../ST-006-meeting-reader-api-for-city-list-and-detail.md)
- Requirement Links: MVP §4.5(1-2), FR-2, FR-6, NFR-2

## Ordered Checklist

- [x] [TASK-ST-006-01](TASK-ST-006-01.md) — Reader Query Index and Contract Prep
- [ ] [TASK-ST-006-02](TASK-ST-006-02.md) — City-Scoped Meetings List Endpoint
- [ ] [TASK-ST-006-03](TASK-ST-006-03.md) — Meeting Detail Endpoint with Evidence Payload
- [ ] [TASK-ST-006-04](TASK-ST-006-04.md) — Home-City Scoping Enforcement
- [ ] [TASK-ST-006-05](TASK-ST-006-05.md) — Reader API Contract and Pagination Test Coverage

## Dependency Chain

- TASK-ST-006-01 -> TASK-ST-006-02
- TASK-ST-006-01 -> TASK-ST-006-03
- TASK-ST-006-02 -> TASK-ST-006-04
- TASK-ST-006-03 -> TASK-ST-006-04
- TASK-ST-006-02 -> TASK-ST-006-05
- TASK-ST-006-03 -> TASK-ST-006-05
- TASK-ST-006-04 -> TASK-ST-006-05

## Validation Commands

- `pytest -q`
