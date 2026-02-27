# Outbox and Attempt Schema

**Task ID:** TASK-ST-009-02  
**Story:** ST-009  
**Bucket:** data  
**Requirement Links:** FR-5, NFR-1, NFR-2, NFR-4

## Objective
Add persistence structures that enforce idempotent logical delivery and capture attempt-level audit data.

## Scope
- In scope:
  - Notification outbox table with dedupe unique constraint.
  - Delivery attempts table with attempt number, outcome, and failure metadata.
  - Status and timestamp columns needed for retry processing.
- Out of scope:
  - Publish-side insert logic.
  - Worker send loop logic.

## Inputs / Dependencies
- TASK-ST-009-01

## Implementation Notes
- Apply unique index on dedupe key.
- Include foreign key from attempts to outbox row.
- Preserve fields needed for triage: error code, provider response summary, next_retry_at.

## Acceptance Criteria
1. Duplicate inserts with same dedupe key are rejected or no-op according to chosen strategy.
2. Attempt rows can store multiple retries for one outbox item.
3. Migration is reversible and does not break existing schema baseline.

## Validation
- Run migration up and down locally.
- Run DB integration test for unique dedupe enforcement.
- Run DB integration test for multiple attempts per outbox record.

## Deliverables
- Migration files.
- Updated data model definitions.
- DB integration tests for constraints and relations.
