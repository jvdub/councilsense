# ST-019 Task Index — Topic Semantic Hardening

- Story: [ST-019 — Phase 1.5: Topic Semantic Hardening](../../ST-019-phase-1-5-topic-semantic-hardening.md)
- Requirement Links: FR-4, GAP_PLAN §Phase 2, GAP_PLAN §Parity Targets (Topic quality), GAP_PLAN §Gate B

## Ordered Checklist

- [x] [TASK-ST-019-01](TASK-ST-019-01-topic-semantic-baseline-and-fixture-gap-matrix.md) — Topic Semantic Baseline and Fixture Gap Matrix
- [x] [TASK-ST-019-02](TASK-ST-019-02-phrase-level-topic-derivation-and-civic-concept-normalization.md) — Phrase-Level Topic Derivation and Civic Concept Normalization
- [x] [TASK-ST-019-03](TASK-ST-019-03-generic-token-suppression-and-3-to-5-topic-bounds.md) — Generic Token Suppression and 3–5 Topic Bounds
- [x] [TASK-ST-019-04](TASK-ST-019-04-topic-to-evidence-mapping-contract-and-fixture-assertions.md) — Topic-to-Evidence Mapping Contract and Fixture Assertions
- [x] [TASK-ST-019-05](TASK-ST-019-05-topic-semantic-gate-b-readiness-and-scorecard-verification.md) — Topic Semantic Gate B Readiness and Scorecard Verification

## Dependency Chain

- TASK-ST-019-01 -> TASK-ST-019-02
- TASK-ST-019-01 -> TASK-ST-019-03
- TASK-ST-019-02 -> TASK-ST-019-04
- TASK-ST-019-03 -> TASK-ST-019-04
- TASK-ST-019-02 -> TASK-ST-019-05
- TASK-ST-019-03 -> TASK-ST-019-05
- TASK-ST-019-04 -> TASK-ST-019-05

## Notes

- Task 01 establishes measurable semantic failure categories so later hardening can be validated against fixtures.
- Tasks 02–04 implement and verify additive hardening only; they must not break existing summary/decision/action contracts.
- Task 05 is the integration checkpoint that proves Gate B topic semantic readiness across fixtures.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`
