# Backend Prompt Eligibility and Grounded Answer Synthesis

**Task ID:** TASK-ST-035-02  
**Story:** ST-035  
**Bucket:** backend  
**Requirement Links:** ST-035 Acceptance Criteria #1, #2, and #3, FR-4, REQUIREMENTS §13.2 Trust Outcome

## Objective

Implement deterministic prompt eligibility and evidence-backed answer synthesis from grounded meeting detail and structured relevance fields.

## Scope

- Evaluate whether each approved prompt can be answered from grounded data.
- Generate short answers and supporting evidence links for eligible prompts.
- Omit prompts when required grounded data is missing or conflicting.
- Out of scope: additive API schema and frontend rendering.

## Inputs / Dependencies

- TASK-ST-035-01 prompt set and answer template rules.
- ST-032 structured resident-relevance extraction outputs.
- ST-033 resident-relevance API projection patterns.

## Implementation Notes

- Keep synthesis deterministic and template-driven.
- Require at least one claim-evidence or evidence-v2 support path per answer.
- Avoid introducing generalized retrieval or conversation state.

## Acceptance Criteria

1. Eligible prompts produce bounded, evidence-backed short answers.
2. Ineligible prompts are omitted cleanly rather than answered speculatively.
3. Answer outputs remain deterministic for unchanged inputs.
4. Supporting evidence linkage is available for each generated answer.

## Validation

- Run prompt generation against meetings with full and sparse structured relevance data.
- Verify omission for unsupported prompt categories.
- Confirm answer content and evidence linkage remain stable across reruns.

## Deliverables

- Backend prompt eligibility logic.
- Grounded short-answer synthesis behavior.
- Evidence linkage mapping for prompt answers.
