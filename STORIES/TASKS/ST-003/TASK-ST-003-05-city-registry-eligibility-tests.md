# Add city registry and eligibility test coverage

**Task ID:** TASK-ST-003-05  
**Story:** ST-003  
**Bucket:** tests  
**Requirement Links:** FR-2, FR-3, FR-7

## Objective
Prove city validation and ingestion eligibility behavior including zero-subscriber scenarios.

## Scope
- Add tests for profile city validation against registry.
- Add tests showing enabled cities are eligible without subscribers.
- Out of scope: end-to-end schedule execution timing tests.

## Inputs / Dependencies
- TASK-ST-003-03
- TASK-ST-003-04

## Implementation Notes
- Target integration tests around profile validation and scheduler input selection.
- Use fixtures for enabled city with and without subscribers.

## Acceptance Criteria
1. Invalid registry city references are rejected in tested flows.
2. Enabled cities with zero subscribers remain eligible for processing input.
3. Disabled cities are excluded from eligibility.

## Validation
- Run story-focused test subset for registry and eligibility modules.
- Confirm all added tests pass in CI/local run.

## Deliverables
- New/updated tests covering ST-003 acceptance behavior.
