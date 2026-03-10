# Source-Scoped Idempotency and Checksum Dedupe

**Task ID:** TASK-ST-023-02  
**Story:** ST-023  
**Bucket:** backend  
**Requirement Links:** ST-023 Scope (source-scoped ingestion/extraction), ST-023 Acceptance Criteria #2-#3, AGENDA_PLAN §5

## Objective

Implement source-scoped idempotency and checksum deduplication so duplicate source payloads do not create duplicate documents, artifacts, or stage outcomes.

## Scope

- Generate idempotency and dedupe keys per city/meeting/source/revision/checksum contract.
- Enforce dedupe checks before persistence and stage transition writes.
- Define duplicate-hit behavior (no-op, existing artifact linkage, diagnostic logging).
- Out of scope: planner logic, frontend/API rendering, and quality-gate policy changes.

## Inputs / Dependencies

- TASK-ST-023-01 bundle identity and source expectations.
- ST-022 idempotency naming contract and additive schema constraints.
- Existing artifact persistence and run-stage state model.

## Implementation Notes

- Ensure key generation is deterministic and order-independent for equivalent payloads.
- Persist dedupe decisions for replay diagnostics.
- Keep operations safe under concurrent worker execution.

## Acceptance Criteria

1. Duplicate source payloads are deduplicated by checksum/idempotency key before creating new artifacts. (ST-023 AC #2)
2. Re-ingesting the same window does not create duplicate documents or artifact records. (ST-023 AC #3)
3. Dedupe decisions are observable via structured diagnostics. (supports testability and operations)

## Validation

- Unit tests for key generation and dedupe branch behavior.
- Integration tests for duplicate payload replay under same bundle.
- Concurrency sanity checks for race-safe no-duplicate outcomes.

## Deliverables

- Source-scoped idempotency/dedupe implementation.
- Duplicate handling diagnostics contract.
- Unit/integration tests for duplicate prevention.
