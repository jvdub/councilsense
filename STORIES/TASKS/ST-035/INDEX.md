# ST-035 Task Index — Evidence-Backed Follow-Up Prompts for Meeting Detail

- Story: [ST-035 — Resident Relevance: Evidence-Backed Follow-Up Prompts for Meeting Detail](../../ST-035-evidence-backed-follow-up-prompts-for-meeting-detail.md)
- Requirement Links: FR-4, REQUIREMENTS §12.2 Summarization & Relevance Service, REQUIREMENTS §12.3 Web App, REQUIREMENTS §12.4 Chat/Q&A Service, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome

## Ordered Checklist

- [x] [TASK-ST-035-01](TASK-ST-035-01-approved-prompt-set-and-answer-template-definition.md) — Approved Prompt Set and Answer Template Definition
- [x] [TASK-ST-035-02](TASK-ST-035-02-backend-prompt-eligibility-and-grounded-answer-synthesis.md) — Backend Prompt Eligibility and Grounded Answer Synthesis
- [x] [TASK-ST-035-03](TASK-ST-035-03-additive-reader-api-contract-for-suggested-prompts-and-answers.md) — Additive Reader API Contract for Suggested Prompts and Answers
- [x] [TASK-ST-035-04](TASK-ST-035-04-meeting-detail-prompt-rendering-and-evidence-linking.md) — Meeting Detail Prompt Rendering and Evidence Linking
- [x] [TASK-ST-035-05](TASK-ST-035-05-tests-for-prompt-presence-omission-and-evidence-backing.md) — Tests for Prompt Presence, Omission, and Evidence-Backing

## Dependency Chain

- TASK-ST-035-01 -> TASK-ST-035-02
- TASK-ST-035-02 -> TASK-ST-035-03
- TASK-ST-035-03 -> TASK-ST-035-04
- TASK-ST-035-02 -> TASK-ST-035-05
- TASK-ST-035-03 -> TASK-ST-035-05
- TASK-ST-035-04 -> TASK-ST-035-05
- TASK-ST-034-02 -> TASK-ST-035-04

## Notes

- Keep prompts bounded to an approved set; this is not a general chat surface.
- Omit prompts entirely when evidence-backed answers are unavailable.
- Reuse existing evidence display conventions so answers remain grounded and reviewable.

## Validation Commands

- `pytest -q`
- `npm --prefix frontend run test`