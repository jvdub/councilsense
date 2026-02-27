# Implement configured city/source selection service

**Task ID:** TASK-ST-003-03  
**Story:** ST-003  
**Bucket:** backend  
**Requirement Links:** FR-3, FR-7

## Objective
Expose reusable service/repository APIs to fetch enabled cities and sources for orchestration and validation.

## Scope
- Implement service methods for enabled city list retrieval.
- Implement per-city enabled source retrieval with metadata.
- Out of scope: scheduler trigger implementation.

## Inputs / Dependencies
- TASK-ST-003-01
- TASK-ST-003-02

## Implementation Notes
- Target repository/service modules used by scheduler and profile validation.
- Keep interfaces small and testable.

## Acceptance Criteria
1. Service returns enabled cities even when no users are subscribed.
2. Service returns source metadata for each enabled city.
3. Disabled cities/sources are excluded consistently.

## Validation
- Run unit tests for enabled/disabled filtering.
- Verify response shape consumed by downstream callers.

## Deliverables
- Repository/service layer code and unit tests.
