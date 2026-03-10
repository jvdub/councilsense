# Discovery Idempotency and Dedupe-Key Enforcement

**Task ID:** TASK-ST-036-04  
**Story:** ST-036  
**Bucket:** backend  
**Requirement Links:** ST-036 Acceptance Criteria #1 and #2, FR-3, NFR-1, NFR-4

## Objective

Enforce idempotent discovery sync behavior so repeated or concurrent discovery runs do not create duplicate discovered-meeting rows.

## Scope

- Define the discovery dedupe key and write-path rules for rerun safety.
- Enforce duplicate suppression under repeated syncs and concurrent writes.
- Emit enough diagnostics to explain duplicate-hit and metadata-refresh branches.
- Out of scope: reader-facing statuses, processing-request idempotency, and admission-control rules.

## Inputs / Dependencies

- TASK-ST-036-01 schema uniqueness constraints.
- TASK-ST-036-03 discovery sync persistence logic.
- ST-023 dedupe and idempotency implementation patterns.

## Implementation Notes

- Keep dedupe keyed to stable source identity rather than display metadata.
- Make duplicate-hit behavior observable for debugging and test assertions.
- Preserve correctness under concurrent scheduler-triggered discovery work.

## Acceptance Criteria

1. Re-running the same discovery window does not create duplicate discovered-meeting rows. (ST-036 AC #2)
2. Concurrent discovery attempts for the same source meeting converge on one canonical row.
3. Dedupe and refresh decisions are diagnosable in tests and logs.

## Validation

- Unit tests for dedupe-key generation and duplicate-hit branches.
- Concurrency-oriented integration checks for repeated discovery writes.
- Verify refreshed metadata updates the canonical row without identity churn.

## Deliverables

- Discovery dedupe-key and idempotent write implementation.
- Diagnostics for duplicate suppression and refresh paths.
- Unit/integration coverage for rerun and concurrent-write safety.
