# ST-017 Task Index — Rubric Freeze and Fixture Scorecard

- Story: [ST-017 — Phase 1.5: Rubric Freeze + Fixture Scorecard](../../ST-017-phase-1-5-rubric-freeze-and-fixture-scorecard.md)
- Requirement Links: GAP_PLAN §Parity Targets, GAP_PLAN §Fixture + Scorecard, GAP_PLAN §Phase 0, GAP_PLAN §Gate B

## Ordered Checklist

- [x] [TASK-ST-017-01](TASK-ST-017-01-fixture-manifest-and-deterministic-loader-coverage.md) — Fixture Manifest and Deterministic Loader Coverage
- [x] [TASK-ST-017-02](TASK-ST-017-02-rubric-threshold-constants-and-parity-assertion-helpers.md) — Rubric Threshold Constants and Parity Assertion Helpers
- [x] [TASK-ST-017-03](TASK-ST-017-03-scorecard-schema-writer-and-parity-dimension-scoring.md) — Scorecard Schema, Writer, and Parity Dimension Scoring
- [x] [TASK-ST-017-04](TASK-ST-017-04-baseline-capture-and-artifact-retention-for-fixture-set.md) — Baseline Capture and Artifact Retention for Fixture Set
- [x] [TASK-ST-017-05](TASK-ST-017-05-rerun-stability-checks-and-gate-b-verification.md) — Rerun Stability Checks and Gate B Verification

## Dependency Chain

- TASK-ST-017-01 -> TASK-ST-017-03
- TASK-ST-017-02 -> TASK-ST-017-03
- TASK-ST-017-03 -> TASK-ST-017-04
- TASK-ST-017-02 -> TASK-ST-017-05
- TASK-ST-017-04 -> TASK-ST-017-05

## Notes

- Task 01 and Task 02 can execute in parallel once fixture sources and parity dimensions are confirmed.
- Task 05 is the integration checkpoint for deterministic behavior and frozen-rubric evidence.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
