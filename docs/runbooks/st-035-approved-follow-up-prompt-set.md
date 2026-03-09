# ST-035 Approved Follow-Up Prompt Set and Answer Template Rules

- Story: ST-035
- Task: TASK-ST-035-01
- Contract version: `st-035-approved-follow-up-prompts-v1`

## Purpose

Freeze the bounded follow-up prompt set for meeting detail so future ST-035 work can synthesize short, evidence-backed resident answers without introducing freeform chat behavior.

This contract is additive to existing meeting detail behavior. It does not create a general Q&A surface, accept user-authored questions, or require retrieval beyond already grounded meeting detail data.

## Guardrails

- Only the approved prompt IDs and exact prompt text below may be emitted.
- Prompt order is fixed and deterministic.
- Answers are short, template-driven, and resident-facing.
- Prefer omission to vague, weakly grounded, or speculative answers.
- Emit at most one answer per prompt ID.
- Do not synthesize a cross-item answer from multiple planned or outcome items.
- Do not use `meeting_date` by itself as an item timeline answer.
- Do not answer with `unknown`, `not available`, apology text, or system-state explanations. Omit the prompt instead.

## Supported meeting scope

- ST-035 prompt generation is meeting-level only.
- A supported prompt answer must refer to the single meeting-level item represented by top-level `structured_relevance`.
- Item-level resident-relevance fields on `planned.items[*]` and `outcomes.items[*]` may inform later stories, but TASK-ST-035-01 does not define per-item prompt variants.
- If top-level `structured_relevance` is absent, all suggested prompts are omitted.

## Prompt order and exact text

| Prompt ID | Exact prompt text | Primary grounded source |
| --------- | ----------------- | ----------------------- |
| `project_identity` | `What project or item is this about?` | `structured_relevance.subject` |
| `location` | `Where does this apply?` | `structured_relevance.location` |
| `disposition` | `What happened at this meeting?` | `structured_relevance.action` with `structured_relevance.subject` when present |
| `scale` | `How large is it?` | `structured_relevance.scale` when the value is magnitude-oriented |
| `timeline` | `What is the timeline?` | temporal `structured_relevance.scale` or a grounded `key_actions[*]` entry |
| `next_step` | `What happens next?` | grounded `key_actions[*]` entry |

Prompt emission always follows the table order above. Unsupported prompts are skipped without changing the order of the remaining emitted prompts.

## Answer rules

### Global answer-shape rules

- Each answer is a single sentence.
- End each answer with a period.
- Do not include markdown, labels, bullets, quoted excerpts, or multiple alternatives.
- Do not use first-person assistant voice such as `I`, `we`, or `you asked`.
- Do not add advisory language such as `residents should`, `likely`, `probably`, or `it appears` unless that wording is already part of the grounded source text and preserved verbatim under the next-step rule.
- Normalize whitespace and terminal punctuation only. Do not paraphrase beyond the template rules below.

### Prompt-specific templates and omission rules

| Prompt ID | Eligibility | Answer template | Omit when |
| --------- | ----------- | --------------- | --------- |
| `project_identity` | `structured_relevance.subject.value` is present and evidence-backed | `{subject}.` | subject is missing, empty, malformed, or lacks a support path |
| `location` | `structured_relevance.location.value` is present and evidence-backed | `It applies to {location}.` | location is missing, empty, malformed, or lacks a support path |
| `disposition` | `structured_relevance.action.value` is present and evidence-backed; prefer `structured_relevance.subject.value` as the anchor | `{subject} was {action}.` | action is missing, empty, malformed, lacks a support path, or subject is unavailable |
| `scale` | `structured_relevance.scale.value` is present, evidence-backed, and materially describes size, quantity, amount, area, vote count, or similar extent rather than time | `The scale in the record is {scale}.` | scale is missing, empty, temporal rather than magnitude-oriented, malformed, or lacks a support path |
| `timeline` | either `structured_relevance.scale.value` is present, evidence-backed, and explicitly temporal, or a grounded `key_actions[*]` entry contains an explicit date or time window | `The timeline in the record is {timeline_phrase}.` | no explicit temporal phrase is available, the only date is the meeting date, the phrase is speculative, or no support path exists |
| `next_step` | the first grounded `key_actions[*]` entry is present and supportable | `{key_action_text}.` | there are no grounded key actions, the action text is procedural noise without resident-facing meaning, or no support path exists |

## Temporal vs magnitude scale split

`structured_relevance.scale` may contain either magnitude-oriented values or temporal values. To keep prompts deterministic and non-duplicative:

- Treat `scale` as eligible only when the value primarily describes size, quantity, money, acreage, unit count, vote count, or similar extent.
- Treat `timeline` as eligible from `structured_relevance.scale` only when the value primarily describes a date, deadline, schedule window, phased period, or completion horizon.
- Never emit both `scale` and `timeline` from the same unchanged raw phrase.
- If the phrase plausibly mixes both time and magnitude and cannot be split without inference, prefer `scale` only when the magnitude is explicit; otherwise omit both.

## Next-step source selection

When `next_step` or `timeline` relies on `key_actions`, use these deterministic rules:

1. Evaluate `key_actions` in existing array order.
2. Select the first entry that is resident-facing, future-oriented, and evidence-backed.
3. Preserve the selected action text verbatim except for whitespace normalization and final-period normalization.
4. Do not merge multiple key actions into one answer.
5. If multiple key actions are grounded but materially different, keep only the first eligible action.

Resident-facing, future-oriented examples include staff returning with a revision, publishing a document, scheduling a hearing, or issuing a follow-up update. Internal-only operator or workflow noise should be omitted.

## Evidence-backing requirements

Every emitted answer must have at least one support path that substantiates the exact value or sentence used in the answer.

### Field-backed prompts

- `project_identity` must be supported by the evidence attached to `structured_relevance.subject`.
- `location` must be supported by the evidence attached to `structured_relevance.location`.
- `disposition` must be supported by the evidence attached to `structured_relevance.action`; when the answer includes `{subject}`, the subject anchor must also be independently grounded.
- `scale` must be supported by the evidence attached to `structured_relevance.scale`.
- `timeline` sourced from `structured_relevance.scale` must be supported by the evidence attached to that same field.

### Key-action-backed prompts

- `next_step` and `timeline` sourced from `key_actions[*]` must be backed by at least one claim-evidence path or evidence-v2 excerpt that substantiates the selected action text.
- A top-level meeting `evidence_references_v2` list by itself is not sufficient unless one of its entries directly supports the selected answer text.
- If support only exists for part of the action sentence, the prompt is omitted rather than shortened by heuristic rewriting.

## Distinction from chat behavior

This prompt set is intentionally not a chat product.

- Prompts are system-defined, not user-authored.
- Prompt wording is frozen and finite.
- Answers do not depend on conversation history, retrieval reformulation, or multi-turn clarification.
- The system does not generate follow-on questions, open-text suggestions, or `ask anything` affordances.
- Unsupported topics are omitted, not answered with conversational fallback text.

## Omission matrix

| Meeting state | Prompt result |
| ------------- | ------------- |
| top-level `structured_relevance` missing | omit all prompts |
| top-level `structured_relevance` present but only `location` is grounded | emit `location` only |
| `subject` and `action` grounded, no temporal or next-step evidence | emit `project_identity`, `disposition`; omit `timeline`, `next_step` |
| `scale` is temporal only | emit `timeline`; omit `scale` |
| `scale` is magnitude only | emit `scale`; omit `timeline` |
| `key_actions` present but unsupported by claim/evidence linkage | omit `next_step` and any key-action-derived `timeline` |
| competing values require synthesis across multiple items | omit the affected prompt |

## Integration notes for downstream tasks

- TASK-ST-035-02 should preserve the prompt IDs and exact prompt text defined here.
- TASK-ST-035-02 should implement omission-first eligibility rather than fallback prose.
- TASK-ST-035-03 should keep the prompt block optional and additive.
- TASK-ST-035-04 should render the prompts as bounded meeting-detail content, not as an input-driven chat control.