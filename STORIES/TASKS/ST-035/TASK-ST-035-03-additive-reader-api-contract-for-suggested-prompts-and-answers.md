# Additive Reader API Contract for Suggested Prompts and Answers

**Task ID:** TASK-ST-035-03  
**Story:** ST-035  
**Bucket:** backend  
**Requirement Links:** ST-035 Acceptance Criteria #1, #3, and #4, FR-4, REQUIREMENTS §12.3 Web App

## Objective

Define the additive reader API contract for suggested follow-up prompts and short answers, including omission behavior and evidence linkage semantics.

## Scope

- Define field-level schema for suggested prompts, answers, and supporting evidence references.
- Define omission and safe-absence behavior for unsupported meetings.
- Preserve compatibility with existing meeting detail consumers.
- Out of scope: UI rendering and test harness implementation.

## Inputs / Dependencies

- TASK-ST-035-02 grounded prompt synthesis behavior.
- ST-033 additive resident-relevance API patterns.

## Implementation Notes

- Keep the contract additive and optional.
- Reuse existing evidence-reference conventions where practical.
- Make omission behavior explicit for unsupported meetings.

## Reader API Contract

### Top-level field

- Meeting detail may emit an optional top-level `suggested_prompts` array when `ST035_API_FOLLOW_UP_PROMPTS_ENABLED=true` and at least one approved prompt has a grounded answer.
- `suggested_prompts` is omitted, not set to `null` or `[]`, when the flag is off or when the meeting has no supported prompt answers.
- The prompt block is additive-only. Existing meeting-detail fields retain their current meaning and clients that ignore `suggested_prompts` remain compatible.

### Prompt entry schema

Each emitted array item uses this contract:

```json
{
  "prompt_id": "project_identity",
  "prompt": "What project or item is this about?",
  "answer": "North Gateway rezoning application.",
  "evidence_references_v2": [
    {
      "evidence_id": "ev-follow-up-subject-2",
      "document_id": "doc-follow-up-subject-2",
      "artifact_id": "artifact-follow-up-subject-2",
      "document_kind": "minutes",
      "section_path": "minutes.section.4",
      "page_start": null,
      "page_end": null,
      "char_start": 18,
      "char_end": 122,
      "precision": "offset",
      "confidence": "high",
      "excerpt": "Council approved the North Gateway rezoning application for the North Gateway District."
    }
  ]
}
```

### Evidence-linking expectations

- Every emitted prompt answer must carry a non-empty `evidence_references_v2` array.
- `project_identity` uses evidence attached to `structured_relevance.subject`.
- `location` uses evidence attached to `structured_relevance.location`.
- `disposition` must include support for both the action phrase and the subject anchor when both appear in the answer.
- `scale` uses evidence attached to `structured_relevance.scale` when the value is magnitude-oriented.
- `timeline` uses either temporal `structured_relevance.scale` evidence or the grounded `key_actions[*]` claim evidence that supports the extracted timeline phrase.
- `next_step` uses grounded `key_actions[*]` claim evidence and is omitted if only internal/operator workflow text is available.

### Presence and omission matrix

| Meeting / flag state                                                                                   | Contract result                                                                               |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `ST035_API_FOLLOW_UP_PROMPTS_ENABLED=false`                                                            | omit `suggested_prompts`                                                                      |
| flag enabled, top-level `structured_relevance` missing                                                 | omit `suggested_prompts`                                                                      |
| flag enabled, top-level `structured_relevance` present but no approved prompt answer is fully grounded | omit `suggested_prompts`                                                                      |
| flag enabled, one or more approved prompts are grounded                                                | emit `suggested_prompts` in frozen prompt order and omit unsupported prompts inside the block |

### Deterministic examples

- Supported and omitted contract fixtures live in `backend/tests/fixtures/st035_follow_up_prompts_additive_contract_examples.json`.
- The supported example captures all six approved prompts with explicit evidence-v2 linkage for every answer.
- The omitted example captures a meeting where publish metadata exists but no approved answer is sufficiently grounded, so `suggested_prompts` is absent.

## Acceptance Criteria

1. Additive prompt-and-answer contract is documented for meeting detail responses.
2. Evidence linkage expectations are explicit for prompt answers.
3. Unsupported meetings omit prompt blocks safely.
4. Existing clients remain compatible when ignoring the new fields.

## Validation

- Review schema examples for supported and unsupported meetings.
- Confirm omission semantics are additive and non-breaking.
- Check alignment with existing meeting detail field patterns.

## Deliverables

- Prompt-and-answer API contract specification.
- Presence/omission matrix for supported vs unsupported meetings.
- Example payloads including evidence linkage.
- Deterministic contract fixtures and route-level tests covering nominal and omitted cases.
