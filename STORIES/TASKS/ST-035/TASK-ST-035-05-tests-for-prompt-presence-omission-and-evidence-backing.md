# Tests for Prompt Presence, Omission, and Evidence-Backing

**Task ID:** TASK-ST-035-05  
**Story:** ST-035  
**Bucket:** tests  
**Requirement Links:** ST-035 Acceptance Criteria #1 through #5, FR-4, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Add backend and frontend verification for deterministic prompt generation, safe omission, evidence linkage, and bounded-scope behavior.

## Scope

- Add backend tests for prompt eligibility and deterministic answer synthesis.
- Add API contract tests for presence and omission semantics.
- Add frontend verification for rendering, omission, and evidence linkage behavior.
- Out of scope: broader Q&A system evaluation beyond the bounded prompt set.

## Inputs / Dependencies

- TASK-ST-035-02 grounded answer synthesis.
- TASK-ST-035-03 prompt-and-answer contract.
- TASK-ST-035-04 frontend rendering.

## Implementation Notes

- Keep assertions focused on bounded prompt behavior and grounding.
- Verify that unsupported meetings do not expose partial or speculative prompt shells.
- Capture both backend and frontend evidence for rollout readiness.

## Acceptance Criteria

1. Tests verify prompt presence for supported meetings and omission for unsupported ones.
2. Deterministic answer synthesis is asserted across repeated runs.
3. Rendered answers preserve evidence linkage and bounded-scope presentation.
4. Regression coverage demonstrates the feature is not behaving like general chat.

## Validation

- `pytest -q`
- `npm --prefix frontend run test`
- Run targeted meeting detail verification suites with prompt fields present and absent.

## Deliverables

- Backend and frontend test coverage for prompt presence and omission.
- Determinism assertions for prompt answers.
- Evidence-linkage verification for rendered prompts.