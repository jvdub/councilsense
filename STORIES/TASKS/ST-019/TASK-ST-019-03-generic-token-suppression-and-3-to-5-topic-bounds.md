# Generic Token Suppression and 3–5 Topic Bounds

**Task ID:** TASK-ST-019-03  
**Story:** ST-019  
**Bucket:** backend  
**Requirement Links:** FR-4, GAP_PLAN §Parity Targets (Topic quality), GAP_PLAN §Gate B

## Objective

Apply configurable suppression and selection rules so notable topics are meaningful and normalized to 3–5 labels when evidence is sufficient.

## Scope

- Add configurable low-information token/phrase suppression for topic candidates.
- Enforce topic output bounds of 3–5 when sufficient high-quality evidence exists.
- Define deterministic fallback behavior when fewer than three qualified topics are available.
- Out of scope: topic-to-evidence mapping enforcement logic (covered in TASK-ST-019-04).

## Inputs / Dependencies

- TASK-ST-019-01 semantic gap matrix.
- Phrase-level derivation outputs from TASK-ST-019-02.

## Implementation Notes

- Suppression configuration should be explicit, reviewable, and easy to extend.
- Selection order and tie-breaking must be deterministic across reruns.
- Keep behavior additive and avoid altering unrelated summarization sections.

## Acceptance Criteria

1. Generic-only labels identified in baseline fixtures are suppressed unless paired with civic context.
2. Fixture outputs emit 3–5 notable topics when enough qualified candidates exist.
3. Runs with unchanged inputs produce stable topic counts and ordering.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Configurable suppression and bounded topic selection behavior integrated into topic generation.
- Fixture evidence demonstrating reduced generic-topic leakage and compliant topic counts.
