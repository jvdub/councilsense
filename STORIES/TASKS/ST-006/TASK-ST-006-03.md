# Meeting Detail Endpoint with Evidence Payload

**Task ID:** TASK-ST-006-03  
**Story:** ST-006  
**Bucket:** backend  
**Requirement Links:** MVP §4.5(2), FR-6, FR-4

## Objective
Implement GET meeting detail endpoint that returns summary, decisions/topics, and evidence pointers with confidence labels.

## Scope (+ Out of scope)
- Implement GET /v1/meetings/{meeting_id}.
- Include summary, key decisions/actions, notable topics, evidence pointers, status/confidence.
- Out of scope: cross-city policy enforcement internals (handled separately).

## Inputs / Dependencies
- ST-005 processed output and evidence schema.
- Authenticated user context.
- Can start once payload contract with ST-005 is stable.

## Implementation Notes
- Keep evidence payload shape faithful to persisted schema.
- Return explicit confidence label for `limited_confidence` meetings.
- Maintain read-only semantics.

## Acceptance Criteria
1. Detail payload includes required sections and evidence pointers.
2. Confidence/status fields are present and consistent with stored state.
3. Endpoint returns predictable not-found behavior for unknown IDs.

## Validation
- Run detail endpoint integration tests with evidence-present and limited-confidence fixtures.
- Validate response schema against API contract.

## Deliverables
- Detail endpoint implementation and schema/contract tests.
