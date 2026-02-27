# Summarization Output Contract

**Task ID:** TASK-ST-005-02  
**Story:** ST-005  
**Bucket:** backend  
**Requirement Links:** MVP §4.3(2-4), FR-4, FR-7(3)

## Objective
Implement generation and persistence of summary, key decisions/actions, and notable topics in a stable output contract.

## Scope (+ Out of scope)
- Build/adjust summarization service output shape for required sections.
- Persist generated sections to the meeting processed record.
- Out of scope: evidence attachment details and quality-gate policy.

## Inputs / Dependencies
- TASK-ST-005-01 schema updates.
- Existing extraction artifacts and LLM orchestration path.
- Upstream dependency: ST-004 processing pipeline.

## Implementation Notes
- Keep contract deterministic and versionable.
- Ensure empty-safe behavior when a section has no content.
- Avoid publishing confidence claims in this step.

## Acceptance Criteria
1. Processed output includes summary, decisions/actions, and notable topics.
2. Persisted shape is stable and retrievable for downstream API usage.
3. Service handles sparse input without runtime failure.

## Validation
- Run targeted backend tests for summarization output shape.
- Execute one end-to-end processing run and verify persisted sections.

## Deliverables
- Updated summarization service and persistence integration.
- Test coverage for output contract fields.
