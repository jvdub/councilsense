# Meeting Detail Prompt Rendering and Evidence Linking

**Task ID:** TASK-ST-035-04  
**Story:** ST-035  
**Bucket:** frontend  
**Requirement Links:** ST-035 Acceptance Criteria #1, #2, and #4, REQUIREMENTS §12.3 Web App, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Render bounded suggested prompts and short answers in meeting detail with clear evidence linkage and safe fallback behavior.

## Scope

- Add a prompt-and-answer section to meeting detail using additive API fields.
- Link each rendered answer to supporting evidence or detailed sections where available.
- Provide neutral omission behavior when prompts are unavailable.
- Out of scope: backend prompt generation and general chat UI.

## Inputs / Dependencies

- TASK-ST-035-03 prompt-and-answer API contract.
- TASK-ST-034-02 resident scan-card rendering and layout integration.
- Existing evidence reference presentation patterns.

## Implementation Notes

- Keep the prompt section bounded and visually distinct from chat.
- Reuse existing evidence and detail navigation affordances where possible.
- Avoid rendering empty prompt shells when the additive data is absent.

## Acceptance Criteria

1. Supported meetings render suggested prompts and evidence-backed short answers.
2. Answers include accessible linkage to supporting evidence when available.
3. Unsupported meetings omit the prompt section cleanly.
4. The UI remains clearly bounded and not chat-like.

## Validation

- Run full, partial, and unsupported prompt payload scenarios.
- Confirm answer evidence links work with keyboard and screen-reader flows.
- Verify omission behavior does not disturb baseline meeting detail layout.

## Deliverables

- Meeting detail prompt-and-answer rendering.
- Evidence-linking affordances for rendered answers.
- Omission and empty-state behavior for unsupported meetings.
