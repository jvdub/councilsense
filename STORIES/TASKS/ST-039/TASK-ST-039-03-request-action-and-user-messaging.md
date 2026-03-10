# Request Action and User Messaging

**Task ID:** TASK-ST-039-03  
**Story:** ST-039  
**Bucket:** frontend  
**Requirement Links:** ST-039 Acceptance Criteria #2 and #3, FR-4, FR-6, NFR-2

## Objective

Wire the request-summary action into meeting tiles and surface clear resident-facing feedback for accepted, duplicate-active, and limit responses.

## Scope

- Implement the request-processing interaction for eligible meeting states.
- Handle accepted, existing-active, and limit/error outcomes from the API.
- Update tile state and user messaging without requiring page breakage or queue-specific knowledge.
- Out of scope: backend admission-control implementation, live progress polling, and operator-facing status details.

## Inputs / Dependencies

- TASK-ST-039-02 tile-state rendering.
- TASK-ST-038-02 admission-control and duplicate-click response semantics.
- Processing-request contract from ST-037.

## Implementation Notes

- Prefer optimistic-but-correct UI transitions that reconcile with API outcomes.
- Keep messaging user-centric and avoid leaking raw backend error semantics.
- Treat duplicate-active outcomes as a success path, not a failure path.

## Acceptance Criteria

1. Eligible tiles can trigger a processing request and update UI state accordingly. (ST-039 AC #3)
2. Duplicate-active and limit responses are surfaced clearly and non-destructively. (ST-039 AC #2 and #3)
3. Request outcomes do not break pagination or navigation state.

## Validation

- Component/page tests for accepted, duplicate-active, and limit/error outcomes.
- Verify tile state transitions remain coherent after request attempts.
- Confirm navigation state is preserved after action handling.

## Deliverables

- Request-summary interaction on meeting tiles.
- User-facing messaging for primary request outcomes.
- Test coverage for request action flows.
