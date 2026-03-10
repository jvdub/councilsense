# Approved Prompt Set and Answer Template Definition

**Task ID:** TASK-ST-035-01  
**Story:** ST-035  
**Bucket:** backend  
**Requirement Links:** ST-035 Acceptance Criteria #1 and #4, FR-4, REQUIREMENTS §12.4 Chat/Q&A Service, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Define the bounded follow-up prompt set and answer template rules for meeting detail so prompt generation remains deterministic, resident-facing, and evidence-backed.

## Scope

- Define the approved prompt categories such as project identity, location, disposition, scale, timeline, and next step.
- Define answer template rules and omission criteria for each prompt type.
- Define evidence-backing expectations for generated answers.
- Out of scope: synthesis implementation and frontend rendering.

## Inputs / Dependencies

- ST-032 structured resident-relevance extraction.
- Existing evidence and meeting detail presentation patterns from ST-006 and ST-007.

## Implementation Notes

- Keep prompts tightly bounded and deterministic.
- Prefer omission to vague or speculative answers.
- Ensure templates can map cleanly to structured relevance fields and evidence references.

## Acceptance Criteria

1. Approved prompt categories are documented and bounded.
2. Each prompt category has explicit answer template and omission rules.
3. Evidence requirements are defined for every answer type.
4. The design remains clearly distinct from freeform chat behavior.

## Validation

- Review prompt set against current meeting detail and structured relevance capabilities.
- Confirm no prompt requires unsupported inference.
- Verify answer templates are specific enough for deterministic generation.

## Deliverables

- Approved follow-up prompt catalog.
- Answer template rules and omission matrix.
- Evidence-backing rules for prompt answers.
