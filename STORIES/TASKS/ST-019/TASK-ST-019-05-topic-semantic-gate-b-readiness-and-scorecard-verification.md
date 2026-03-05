# Topic Semantic Gate B Readiness and Scorecard Verification

**Task ID:** TASK-ST-019-05  
**Story:** ST-019  
**Bucket:** ops  
**Requirement Links:** FR-4, GAP_PLAN §Gate B, GAP_PLAN §Parity Targets (Topic quality)

## Objective

Run end-to-end verification that topic semantic hardening meets fixture thresholds and is ready for Gate B report-only/enforced operation.

## Scope

- Execute full fixture scorecard and collect topic semantic threshold outcomes.
- Confirm no regressions in summary/decision/action contract behavior while topic quality improves.
- Document release-readiness notes, residual risks, and rollback triggers for topic hardening changes.
- Out of scope: introducing additional hardening features not required by ST-019 acceptance criteria.

## Inputs / Dependencies

- TASK-ST-019-02 phrase-level derivation and normalization.
- TASK-ST-019-03 suppression and bounds.
- TASK-ST-019-04 topic evidence mapping enforcement.

## Implementation Notes

- Use the same fixture set and scoring mode intended for Gate B quality evaluation.
- Compare outcomes against TASK-ST-019-01 baseline to show measurable improvement.
- Record exact command invocations and result artifact locations for reproducibility.

## Acceptance Criteria

1. Topic semantic thresholds pass across baseline fixtures in scorecard evaluation.
2. All emitted topics retain required evidence mappings in final verification output.
3. Verification notes document pass/fail status, residual edge cases, and operational go/no-go recommendation.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Gate B readiness verification notes for ST-019 with reproducible evidence.
- Final story-level summary of threshold status and residual risk handling.
