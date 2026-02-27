# Push Capability and Contract Discovery

**Task ID:** TASK-ST-008-01  
**Story:** ST-008  
**Bucket:** docs  
**Requirement Links:** MVP §4.4(2-5), FR-5(4-5), NFR-3

## Objective
Resolve prerequisite unknowns for browser push support, permission-state UX expectations, and backend subscription API contract details.

## Scope (+ Out of scope)
- Confirm supported browser capability matrix for service worker and PushManager behavior.
- Confirm required backend request/response contract for subscription create/read/delete and state flags.
- Define state mapping for invalid/expired/suppressed to recovery actions.
- Out of scope: implementing UI or API code.

## Inputs / Dependencies
- Existing settings UI architecture.
- Backend notification/subscription API definitions.
- No code task dependency.

## Implementation Notes
- Keep outcomes concise and implementation-ready.
- Record explicit fallback behavior for unsupported/denied scenarios.
- Document only MVP push channel; exclude email controls.

## Acceptance Criteria
1. Documented capability matrix is sufficient to implement push UX without ambiguity.
2. Subscription API contract and state mappings are finalized.
3. Recovery actions for invalid/expired/suppressed states are explicitly defined.

## Validation
- Review sign-off from frontend and backend owners on discovery artifact.
- Verify no unresolved MVP-blocking unknowns remain.

## Deliverables
- Short discovery note/ADR with capability matrix and contract decisions.
