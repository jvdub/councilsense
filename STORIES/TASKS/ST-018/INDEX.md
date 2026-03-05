# ST-018 Task Index — Additive evidence_references Contract

- Story: [ST-018 — Phase 1.5: Additive evidence_references Contract](../../ST-018-phase-1-5-additive-evidence-references-contract.md)
- Requirement Links: GAP_PLAN §Phase 1, GAP_PLAN §Gate A, MVP §4.5(1-2), FR-6, NFR-2

## Ordered Checklist

- [x] [TASK-ST-018-01](TASK-ST-018-01-meeting-detail-evidence-references-contract-decision.md) — Meeting Detail evidence_references Contract Decision
- [x] [TASK-ST-018-02](TASK-ST-018-02-additive-evidence-references-projection-and-serialization.md) — Additive evidence_references Projection and Serialization
- [x] [TASK-ST-018-03](TASK-ST-018-03-evidence-present-and-evidence-sparse-fixture-contract-tests.md) — Evidence-Present and Evidence-Sparse Fixture Contract Tests
- [x] [TASK-ST-018-04](TASK-ST-018-04-legacy-field-compatibility-and-gate-a-regression-suite.md) — Legacy Field Compatibility and Gate A Regression Suite
- [x] [TASK-ST-018-05](TASK-ST-018-05-api-contract-release-notes-and-verification-runbook.md) — API Contract Release Notes and Verification Runbook

## Dependency Chain

- TASK-ST-018-01 -> TASK-ST-018-02
- TASK-ST-018-01 -> TASK-ST-018-03
- TASK-ST-018-02 -> TASK-ST-018-03
- TASK-ST-018-02 -> TASK-ST-018-04
- TASK-ST-018-03 -> TASK-ST-018-04
- TASK-ST-018-04 -> TASK-ST-018-05

## Notes

- Task 01 freezes the additive contract decision for empty/omitted behavior before implementation-specific testing.
- Task 04 is the primary safety gate for backward compatibility and Gate A readiness.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
