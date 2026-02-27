# Processing Version Provenance

**Task ID:** TASK-ST-010-03  
**Story:** ST-010  
**Bucket:** backend  
**Requirement Links:** FR-7, NFR-4

## Objective
Capture parser and source version metadata in processing runs for reproducibility.

## Scope
- In scope:
  - Persist parser_version and source_version on run records.
  - Ensure metadata is attached for each processed run.
  - Expose provenance in internal read/query path.
- Out of scope:
  - External UI polish.

## Inputs / Dependencies
- ST-004 run lifecycle persistence

## Implementation Notes
- Use stable version string format.
- Persist values even when processing partially fails.
- Include migration-safe defaults for historical rows.

## Acceptance Criteria
1. New processing runs store parser and source version fields.
2. Querying a run returns both version values.
3. Historical rows remain readable after migration.

## Validation
- Run migration tests with seeded historical data.
- Run integration test verifying version fields persisted per run.

## Deliverables
- Schema and persistence updates.
- Run query response updates.
- Provenance-focused tests.
