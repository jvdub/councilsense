# ST-026 Task Index — Evidence v2 Linkage, Precision Ladder, and Deterministic Ordering

- Story: [ST-026 — Evidence v2 Linkage, Precision Ladder, and Deterministic Ordering](../../ST-026-evidence-v2-linkage-precision-ladder-and-deterministic-ordering.md)
- Requirement Links: AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision, AGENDA_PLAN §6 Testing and validation plan

## Ordered Checklist

- [x] [TASK-ST-026-01](TASK-ST-026-01-claim-to-canonical-document-and-span-linkage-contract.md) — Claim-to-Canonical Document/Span Linkage Contract
- [x] [TASK-ST-026-02](TASK-ST-026-02-precision-ladder-ranking-and-deterministic-evidence-ordering.md) — Precision Ladder Ranking and Deterministic Evidence Ordering
- [x] [TASK-ST-026-03](TASK-ST-026-03-additive-evidence-references-v2-projection-and-compatibility-gating.md) — Additive `evidence_references_v2` Projection and Compatibility Gating
- [x] [TASK-ST-026-04](TASK-ST-026-04-contract-fixtures-and-rerun-stability-snapshot-verification.md) — Contract Fixtures and Rerun Stability Snapshot Verification
- [x] [TASK-ST-026-05](TASK-ST-026-05-precision-distribution-diagnostics-and-scorecard-reporting.md) — Precision Distribution Diagnostics and Scorecard Reporting

## Dependency Chain

- TASK-ST-026-01 -> TASK-ST-026-02
- TASK-ST-026-01 -> TASK-ST-026-03
- TASK-ST-026-02 -> TASK-ST-026-03
- TASK-ST-026-02 -> TASK-ST-026-04
- TASK-ST-026-03 -> TASK-ST-026-04
- TASK-ST-026-02 -> TASK-ST-026-05
- TASK-ST-026-03 -> TASK-ST-026-05

## Notes

- Task 01 establishes the canonical linkage contract so downstream ranking/projection tasks can remain additive and deterministic.
- Tasks 02 and 03 implement the core ST-026 acceptance behavior: stable ordering and primary `evidence_references_v2` projection.
- Tasks 04 and 05 provide release evidence for contract stability and measurable precision improvements beyond file-level references.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`
