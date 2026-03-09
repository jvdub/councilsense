# ST-033 Task Index — Resident Relevance Reader API Additive Fields

- Story: [ST-033 — Resident Relevance: Reader API Additive Subject, Location, and Impact Fields](../../ST-033-reader-api-additive-resident-relevance-fields.md)
- Requirement Links: FR-4, FR-6, REQUIREMENTS §12.2 Summarization & Relevance Service, REQUIREMENTS §12.3 Web App, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.5 Clarity Outcome, REQUIREMENTS §14(3,10)

## Ordered Checklist

- [x] [TASK-ST-033-01](TASK-ST-033-01-additive-reader-api-contract-for-resident-relevance-fields.md) — Additive Reader API Contract for Resident-Relevance Fields
- [x] [TASK-ST-033-02](TASK-ST-033-02-feature-flag-wiring-and-flag-off-baseline-parity-guards.md) — Feature Flag Wiring and Flag-Off Baseline Parity Guards
- [x] [TASK-ST-033-03](TASK-ST-033-03-resident-relevance-projection-and-deterministic-serialization.md) — Resident-Relevance Projection and Deterministic Serialization
- [x] [TASK-ST-033-04](TASK-ST-033-04-contract-fixtures-for-nominal-sparse-and-missing-data-cases.md) — Contract Fixtures for Nominal, Sparse, and Missing-Data Cases
- [x] [TASK-ST-033-05](TASK-ST-033-05-backwards-compatibility-and-latency-regression-checks.md) — Backwards-Compatibility and Latency Regression Checks

## Dependency Chain

- TASK-ST-033-01 -> TASK-ST-033-02
- TASK-ST-033-02 -> TASK-ST-033-03
- TASK-ST-033-03 -> TASK-ST-033-04
- TASK-ST-033-03 -> TASK-ST-033-05
- TASK-ST-033-04 -> TASK-ST-033-05
- TASK-ST-032-04 -> TASK-ST-033-03

## Notes

- Keep resident-relevance fields additive and safely omittable for legacy consumers.
- Preserve flag-off baseline parity at the response-shape level.
- Reuse existing additive API and evidence v2 conventions where practical.

## Validation Commands

- `pytest -q`
- `python -m pytest -q backend/tests/test_meeting_detail_api.py`