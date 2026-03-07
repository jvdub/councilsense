# ST-027 Task Index — Reader API Additive Planned/Outcomes and Mismatch Fields

- Story: [ST-027 — Reader API Additive Planned/Outcomes and Mismatch Fields](../../ST-027-reader-api-additive-planned-outcomes-and-mismatch-fields.md)
- Requirement Links: AGENDA_PLAN §3 Target architecture (API), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches, AGENDA_PLAN §6 Testing and validation plan

## Ordered Checklist

- [x] [TASK-ST-027-01](TASK-ST-027-01-additive-reader-api-contract-for-planned-outcomes-and-mismatch-blocks.md) — Additive Reader API Contract for Planned/Outcomes/Mismatch Blocks
- [ ] [TASK-ST-027-02](TASK-ST-027-02-feature-flag-wiring-and-flag-off-baseline-parity-guards.md) — Feature Flag Wiring and Flag-Off Baseline Parity Guards
- [ ] [TASK-ST-027-03](TASK-ST-027-03-meeting-detail-serializer-extension-for-additive-fields.md) — Meeting Detail Serializer Extension for Additive Fields
- [ ] [TASK-ST-027-04](TASK-ST-027-04-flag-state-contract-and-integration-test-matrix.md) — Flag-State Contract and Integration Test Matrix
- [ ] [TASK-ST-027-05](TASK-ST-027-05-detail-endpoint-latency-regression-checks-and-release-evidence.md) — Detail Endpoint Latency Regression Checks and Release Evidence

## Dependency Chain

- TASK-ST-027-01 -> TASK-ST-027-02
- TASK-ST-027-01 -> TASK-ST-027-03
- TASK-ST-027-02 -> TASK-ST-027-03
- TASK-ST-027-03 -> TASK-ST-027-04
- TASK-ST-027-03 -> TASK-ST-027-05
- TASK-ST-027-04 -> TASK-ST-027-05
- TASK-ST-026-03 -> TASK-ST-027-03

## Notes

- Task 01 freezes additive API field semantics so serializer/test tasks can enforce backwards-safe behavior.
- Tasks 02 and 03 ensure default flag-off parity and controlled additive exposure for planned/outcomes/mismatch blocks.
- Tasks 04 and 05 provide regression evidence for both contract safety and p95 latency budget adherence.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
