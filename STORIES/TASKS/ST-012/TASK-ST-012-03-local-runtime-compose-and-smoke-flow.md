# Local Runtime Compose and Smoke Flow

**Task ID:** TASK-ST-012-03  
**Story:** ST-012  
**Bucket:** ops  
**Requirement Links:** NFR-5

## Objective
Provide a local runtime that executes the full MVP flow with minimal setup.

## Scope
- In scope:
  - Local compose or equivalent runtime scripts for web, api, worker, db, storage, queue adapter.
  - Seed and startup scripts for fast developer onboarding.
  - End-to-end smoke flow for signup, onboarding, process, reader, and notification path.
- Out of scope:
  - Cloud deployment.

## Inputs / Dependencies
- TASK-ST-012-02
- ST-007 reader flow
- ST-009 notification flow

## Implementation Notes
- Keep startup command surface small and documented.
- Use deterministic local fixture data where possible.
- Ensure local queue adapter preserves idempotency semantics.

## Acceptance Criteria
1. Developer can launch full local stack with documented commands.
2. Smoke flow passes across core user journey.
3. Local runtime preserves expected reliability behavior for retries/idempotency.

## Validation
- Run local smoke script end-to-end.
- Run repeated smoke to verify idempotent behavior under rerun.

## Deliverables
- Runtime orchestration files/scripts.
- Local smoke test script and fixtures.
- Quickstart section in docs.
