# ST-037 Task Index — Source Catalog: Reader API and Queue-or-Return Processing Request Contract

- Story: [ST-037 — Source Catalog: Reader API and Queue-or-Return Processing Request Contract](../../ST-037-source-catalog-reader-api-and-queue-or-return-processing-request-contract.md)
- Requirement Links: FR-4, FR-6, NFR-2, NFR-4

## Ordered Checklist

- [ ] [TASK-ST-037-01](TASK-ST-037-01-reader-api-payload-design-for-discovered-meetings-and-processing-status.md) — Reader API Payload Design for Discovered Meetings and Processing Status
- [ ] [TASK-ST-037-02](TASK-ST-037-02-city-scoped-meetings-list-query-over-discovered-and-processed-projections.md) — City-Scoped Meetings List Query Over Discovered and Processed Projections
- [ ] [TASK-ST-037-03](TASK-ST-037-03-processing-request-endpoint-with-queue-or-return-idempotency.md) — Processing-Request Endpoint with Queue-or-Return Idempotency
- [ ] [TASK-ST-037-04](TASK-ST-037-04-contract-and-integration-tests-for-pagination-scope-and-idempotent-requests.md) — Contract and Integration Tests for Pagination, Scope, and Idempotent Requests
- [ ] [TASK-ST-037-05](TASK-ST-037-05-api-documentation-and-processing-request-outcome-semantics.md) — API Documentation and Processing-Request Outcome Semantics

## Dependency Chain

- TASK-ST-037-01 -> TASK-ST-037-02
- TASK-ST-037-01 -> TASK-ST-037-03
- TASK-ST-036-01 -> TASK-ST-037-02
- TASK-ST-036-03 -> TASK-ST-037-03
- TASK-ST-037-02 -> TASK-ST-037-04
- TASK-ST-037-03 -> TASK-ST-037-04
- TASK-ST-037-03 -> TASK-ST-037-05
- TASK-ST-037-04 -> TASK-ST-037-05

## Notes

- Keep the reader contract additive so current meeting detail flows remain intact.
- Freeze the user-visible processing states here so ST-038 and ST-039 can build on a stable contract.
- Defer admission-control policy and active-work dedupe enforcement details to ST-038.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api pytest -q`
