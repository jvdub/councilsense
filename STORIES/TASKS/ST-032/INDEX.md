# ST-032 Task Index — Resident Relevance Structured Subject, Location, and Impact Extraction

- Story: [ST-032 — Resident Relevance: Structured Subject, Location, and Impact Extraction](../../ST-032-resident-relevance-structured-subject-location-and-impact-extraction.md)
- Requirement Links: FR-4, REQUIREMENTS §12.2 Summarization & Relevance Service, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome, REQUIREMENTS §14(10-11)

## Ordered Checklist

- [x] [TASK-ST-032-01](TASK-ST-032-01-structured-relevance-data-model-and-internal-fields.md) — Structured Relevance Data Model and Internal Fields
- [x] [TASK-ST-032-02](TASK-ST-032-02-anchor-harvesting-and-synthesis-for-subject-location-action-scale.md) — Anchor Harvesting and Synthesis for Subject, Location, Action, and Scale
- [x] [TASK-ST-032-03](TASK-ST-032-03-deterministic-evidence-backed-impact-classification.md) — Deterministic Evidence-Backed Impact Classification
- [x] [TASK-ST-032-04](TASK-ST-032-04-carry-through-rules-and-limited-confidence-behavior.md) — Carry-Through Rules and Limited-Confidence Behavior
- [x] [TASK-ST-032-05](TASK-ST-032-05-fixture-coverage-specificity-and-determinism-tests.md) — Fixture Coverage, Specificity, and Determinism Tests

## Dependency Chain

- TASK-ST-032-01 -> TASK-ST-032-02
- TASK-ST-032-01 -> TASK-ST-032-03
- TASK-ST-032-02 -> TASK-ST-032-04
- TASK-ST-032-03 -> TASK-ST-032-04
- TASK-ST-032-04 -> TASK-ST-032-05

## Notes

- Keep structured relevance extraction additive to the existing summarization path; do not regress current publication continuity.
- Prefer deterministic and explainable classification over broad heuristic inference.
- Preserve limited-confidence behavior whenever structured specificity is weak, missing, or conflicting.

## Validation Commands

- `pytest -q`
- `python -m pytest -q backend/tests/test_st020_specificity_and_evidence_precision_hardening.py`
