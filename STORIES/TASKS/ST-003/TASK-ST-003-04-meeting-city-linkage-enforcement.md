# Enforce mandatory city linkage in meeting writes

**Task ID:** TASK-ST-003-04  
**Story:** ST-003  
**Bucket:** backend  
**Requirement Links:** FR-3, FR-7

## Objective
Guarantee every meeting record is linked to a valid city at creation/upsert time.

## Scope
- Require `city_id` in meeting creation/upsert paths.
- Validate `city_id` against configured registry before persistence.
- Out of scope: pipeline scheduling cadence.

## Inputs / Dependencies
- TASK-ST-003-03
- Existing meeting ingest/upsert code paths

## Implementation Notes
- Target meeting repository/service and ingest adapters.
- Keep failure mode explicit for unknown/disabled city references.

## Acceptance Criteria
1. Meeting persistence fails when `city_id` is missing.
2. Meeting persistence fails when `city_id` is invalid/unconfigured.
3. Successful writes always include valid city linkage.

## Validation
- Run integration tests for valid and invalid meeting payloads.
- Verify DB constraints and service-level checks both protect writes.

## Deliverables
- Updated meeting write logic and validation coverage.
