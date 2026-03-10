# ST-036 Task Index — Source Catalog: Discovered Meetings Registry and Sync Baseline

- Story: [ST-036 — Source Catalog: Discovered Meetings Registry and Sync Baseline](../../ST-036-source-catalog-discovered-meetings-registry-and-sync-baseline.md)
- Requirement Links: FR-3, FR-6, FR-7, NFR-1, NFR-4

## Ordered Checklist

- [ ] [TASK-ST-036-01](TASK-ST-036-01-discovered-meetings-schema-and-source-identity-contract.md) — Discovered-Meetings Schema and Source-Identity Contract
- [ ] [TASK-ST-036-02](TASK-ST-036-02-provider-adapters-for-source-meeting-enumeration.md) — Provider Adapters for Source Meeting Enumeration
- [ ] [TASK-ST-036-03](TASK-ST-036-03-discovery-sync-persistence-and-local-meeting-reconciliation.md) — Discovery Sync Persistence and Local-Meeting Reconciliation
- [ ] [TASK-ST-036-04](TASK-ST-036-04-discovery-idempotency-and-dedupe-key-enforcement.md) — Discovery Idempotency and Dedupe-Key Enforcement
- [ ] [TASK-ST-036-05](TASK-ST-036-05-integration-tests-for-discovery-reruns-and-provider-parsing.md) — Integration Tests for Discovery Reruns and Provider Parsing

## Dependency Chain

- TASK-ST-036-01 -> TASK-ST-036-02
- TASK-ST-036-01 -> TASK-ST-036-03
- TASK-ST-036-02 -> TASK-ST-036-03
- TASK-ST-036-01 -> TASK-ST-036-04
- TASK-ST-036-03 -> TASK-ST-036-04
- TASK-ST-036-02 -> TASK-ST-036-05
- TASK-ST-036-04 -> TASK-ST-036-05

## Notes

- Keep the discovered-meetings registry additive to the existing `meetings` and processing-run model.
- Treat CivicClerk as the pilot provider, but keep source-enumeration interfaces extensible.
- Defer reader payload semantics and request endpoint behavior to ST-037.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api pytest -q`
