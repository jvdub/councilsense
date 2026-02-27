# Create city and city-source schema foundations

**Task ID:** TASK-ST-003-01  
**Story:** ST-003  
**Bucket:** data  
**Requirement Links:** FR-3, FR-7, NFR-5

## Objective
Establish normalized schema for configured cities and per-city source metadata with required constraints.

## Scope
- Create/verify `cities` and `city_sources` schema and keys.
- Enforce enabled-state and required metadata constraints.
- Out of scope: scheduler and ingestion execution logic.

## Inputs / Dependencies
- Existing DB migration framework
- Current meeting model constraints

## Implementation Notes
- Target migration files and ORM/model definitions.
- Include indexes needed for enabled-city/source lookups.

## Acceptance Criteria
1. `cities` and `city_sources` tables exist with expected constraints.
2. Schema supports multiple cities while default pilot city can be enabled.
3. Migration applies without drift/regression in local dev DB.

## Validation
- Run migration status/apply checks.
- Run DB unit/repository smoke tests for insert/query constraints.

## Deliverables
- New/updated migrations and schema definitions.
