# Topic-to-Evidence Mapping Contract and Fixture Assertions

**Task ID:** TASK-ST-019-04  
**Story:** ST-019  
**Bucket:** tests  
**Requirement Links:** FR-4, GAP_PLAN §Gate B, ST-018 additive evidence mapping contract

## Objective

Guarantee that every emitted topic has at least one supporting evidence mapping and enforce that rule with fixture assertions.

## Scope

- Extend validation checks so topic entries require at least one evidence mapping.
- Add or update fixture assertions to fail when a topic lacks supporting evidence.
- Ensure topic evidence mapping remains additive and compatible with existing reader contracts.
- Out of scope: introducing new reader payload fields beyond established additive contracts.

## Inputs / Dependencies

- TASK-ST-019-02 derived topic outputs.
- TASK-ST-019-03 suppression and bounded selection behavior.
- ST-018 additive evidence reference patterns.

## Implementation Notes

- Prefer contract tests that validate both presence and pointer shape/consistency.
- Keep failure messages explicit so missing evidence is easy to triage per topic.
- Avoid non-deterministic pointer ordering in test expectations.

## Acceptance Criteria

1. Any topic without at least one evidence mapping causes fixture validation failure.
2. Fixtures that pass include evidence mappings for all emitted topics.
3. Topic evidence checks are compatible with existing additive evidence contract expectations.

## Validation

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.eval.scorecard --fixture-set baseline`

## Deliverables

- Enforced topic-to-evidence mapping checks in test/scorecard paths.
- Fixture validation evidence showing complete topic evidence coverage.
