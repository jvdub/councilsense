# Phrase-Level Topic Derivation and Civic Concept Normalization

**Task ID:** TASK-ST-019-02  
**Story:** ST-019  
**Bucket:** backend  
**Requirement Links:** FR-4, GAP_PLAN §Phase 2, GAP_PLAN §Parity Targets (Topic quality)

## Objective

Implement phrase-level topic derivation that emits civic concept labels rather than verb-only or generic tokens.

## Scope

- Add derivation logic that constructs topic candidates from decision/action/claim context at phrase level.
- Normalize selected labels to civic concept wording suitable for end-user display.
- Out of scope: suppression thresholds, topic count bounds, and evidence-mapping enforcement details handled in later tasks.

## Inputs / Dependencies

- TASK-ST-019-01 baseline categories and examples.
- Existing summarization/topic generation pipeline contracts.

## Implementation Notes

- Preserve current payload schema and field names; only harden label semantics.
- Keep normalization deterministic for identical source inputs.
- Favor existing NLP/parsing primitives already used in pipeline modules.

## Acceptance Criteria

1. Topic candidates are derived from phrase-level civic context instead of single generic tokens.
2. Fixture outputs show improved concept labeling on previously identified weak examples from TASK-ST-019-01.
3. Existing summary, decision, and action response contracts remain backward compatible.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Updated topic derivation and normalization implementation.
- Regression evidence showing semantic improvement on baseline weak-topic fixtures.
