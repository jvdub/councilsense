# Resident Relevance: Evidence-Backed Follow-Up Prompts for Meeting Detail

**Story ID:** ST-035  
**Phase:** Phase 4 (Resident relevance + explainability)  
**Requirement Links:** FR-4, §12.2 Summarization & Relevance Service, §12.3 Web App, §12.4 Chat/Q&A Service, §13.1 Resident Outcome, §13.2 Trust Outcome, §13.5 Clarity Outcome

## User Story

As a resident, I want a few evidence-backed follow-up prompts on a meeting page so I can quickly answer obvious next questions like what project this is, where it is, and what changed without needing a full chat product.

## Scope

- Generate a constrained set of follow-up prompts and short answers from grounded meeting detail and structured relevance fields.
- Limit responses to evidence-backed prompts such as project identity, location, disposition, scale, timeline, and next step when available.
- Present prompts as additive meeting detail content, not as open-ended chat.
- Explicitly exclude unrestricted conversational Q&A, retrieval orchestration, and a standalone chat surface.

## Acceptance Criteria

1. Meetings with sufficient grounded relevance data expose a deterministic set of suggested follow-up prompts and short answers.
2. Every generated answer is backed by at least one evidence reference or claim-evidence path.
3. Prompts are omitted when the required grounded data is unavailable rather than generating speculative answers.
4. Prompt generation remains bounded to an approved question set and does not behave like freeform chat.
5. API and UI tests cover prompt presence, omission, and evidence-backing behavior.

## Implementation Tasks

- [ ] Define the approved follow-up prompt set and answer templates.
- [ ] Implement backend prompt eligibility and answer synthesis from grounded meeting data.
- [ ] Add additive API fields for suggested prompts and evidence-backed short answers.
- [ ] Render prompts in meeting detail with clear evidence and empty-state behavior.
- [ ] Add tests for deterministic prompt generation, safe omission, and bounded-scope behavior.

## Dependencies

- ST-032
- ST-033
- ST-034

## Definition of Done

- Meeting detail can offer bounded, evidence-backed follow-up prompts without introducing a general chat dependency.
- Prompt answers remain grounded, deterministic, and safely omitted when evidence is insufficient.
- The feature is explicitly scoped so future Q&A work can extend it without reworking the reader baseline.
