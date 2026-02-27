# Meetings Reader Client and Models

**Task ID:** TASK-ST-007-01  
**Story:** ST-007  
**Bucket:** frontend  
**Requirement Links:** MVP §4.5(1-3), FR-4, NFR-2

## Objective
Create frontend data-access and typed models for meetings list/detail, including evidence pointers and confidence labels.

## Scope (+ Out of scope)
- Add API client methods for city meetings list and meeting detail.
- Define typed response models used by list/detail pages.
- Include fields for confidence status and evidence references.
- Out of scope: rendering page layouts.

## Inputs / Dependencies
- ST-006 endpoint contracts.
- Authenticated session context from ST-001.

## Implementation Notes
- Keep client error typing explicit for UI state handling.
- Preserve backend confidence values without remapping ambiguity.
- Centralize fetch/retry behavior for both pages.

## Acceptance Criteria
1. Client can fetch list and detail payloads with expected typed shapes.
2. Models include summary, decisions/topics, evidence, and confidence fields.
3. Error states are surfaced in a form usable by pages.

## Validation
- Run frontend unit tests for API client and model parsing.
- Verify contract compatibility against example API fixtures.

## Deliverables
- Reader client module and typed model definitions.
- Unit tests for success and error parsing paths.
