# Add retry policy and failure isolation behavior

**Task ID:** TASK-ST-004-04  
**Story:** ST-004  
**Bucket:** backend  
**Requirement Links:** NFR-1, NFR-2, FR-7(4)

## Objective
Make stage failures retryable and isolated so one city/source failure does not block others.

## Scope
- Classify transient vs permanent errors for retry decisions.
- Implement bounded retries and terminal failure marking.
- Ensure one city/source failure does not halt unrelated city pipelines.
- Out of scope: notification DLQ replay workflows beyond this story.

## Inputs / Dependencies
- TASK-ST-004-03

## Implementation Notes
- Target worker error handling, queue retry config, and run status updater.
- Ensure retry exhaustion maps to deterministic final status.

## Acceptance Criteria
1. Transient failures retry up to configured limit.
2. Permanent failures skip retry and mark run failed directly.
3. Failure in one city/source does not stop processing of other cities.

## Validation
- Run integration tests simulating transient and permanent errors.
- Verify independent city runs continue during a parallel failure scenario.

## Deliverables
- Retry/error-classification implementation and isolation safeguards.
