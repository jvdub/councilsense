# Add profile preferences integration tests

**Task ID:** TASK-ST-002-05  
**Story:** ST-002  
**Bucket:** tests  
**Requirement Links:** FR-2, FR-5(4), FR-6, NFR-3

## Objective
Cover API and behavior transitions for profile updates, authz, and pause semantics.

## Scope
- Add tests for `GET/PATCH /v1/me` happy paths.
- Add tests for invalid city, invalid pause payload, and cross-user access.
- Out of scope: notification delivery channel tests.

## Inputs / Dependencies
- TASK-ST-002-03
- TASK-ST-002-04

## Implementation Notes
- Target integration suite where profile/auth tests already live.
- Reuse fixtures for multi-user scenarios and pause-window timestamps.

## Acceptance Criteria
1. Self-only access constraints are enforced in tests.
2. Pause/unpause transitions persist and evaluate correctly.
3. Validation errors return expected status and error contract.

## Validation
- Run story-specific integration test selection in local/CI.
- Confirm new tests are deterministic and pass consistently.

## Deliverables
- New or updated integration test files for ST-002.
