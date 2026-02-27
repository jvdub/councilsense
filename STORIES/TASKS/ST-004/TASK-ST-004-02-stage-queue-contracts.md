# Define pipeline stage queue contracts

**Task ID:** TASK-ST-004-02  
**Story:** ST-004  
**Bucket:** backend  
**Requirement Links:** MVP §4.3(1-3), NFR-2

## Objective
Standardize async job payload contracts across ingest, extract, summarize, and publish handoff stages.

## Scope
- Define payload schemas for each stage.
- Implement producer/consumer validation at stage boundaries.
- Out of scope: retry policy tuning and DLQ strategy details.

## Inputs / Dependencies
- TASK-ST-004-01
- Existing queue framework and worker conventions

## Implementation Notes
- Target queue message schema modules and stage worker adapters.
- Include run/city/meeting correlation identifiers in all stage messages.

## Acceptance Criteria
1. Each stage has explicit validated payload schema.
2. Stage handoffs preserve required correlation identifiers.
3. Invalid payloads are rejected with explicit error handling path.

## Validation
- Run contract tests for each stage payload schema.
- Execute worker unit tests for valid vs invalid message behavior.

## Deliverables
- Queue contract definitions and stage boundary validation code.
