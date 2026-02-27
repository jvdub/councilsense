# Parser Version Tracking and Drift Event Model

**Task ID:** TASK-ST-016-03  
**Story:** ST-016  
**Bucket:** backend  
**Requirement Links:** NFR-4, ST-016 Acceptance Criteria #2 and #5

## Objective
Record parser version metadata and produce queryable drift events over time for source/parser changes.

## Scope
- Persist parser version at run and source-processing boundaries.
- Define drift event generation when parser behavior/outputs deviate.
- Provide query path for drift trend analysis.
- Out of scope: freshness alert rules and dashboard visualizations.

## Inputs / Dependencies
- TASK-ST-016-01 required metadata fields.
- Existing parser metadata pipeline from ingestion/extraction flow.

## Implementation Notes
- Drift event should include baseline version, current version, and delta context.
- Preserve run identifiers for traceability into incident triage.
- Keep event schema stable and versioned.

## Acceptance Criteria
1. Parser version is recorded for relevant processing runs.
2. Drift events are generated and stored when drift criteria are met.
3. Drift records are queryable by city, source, parser version, and date range.
4. Event schema includes sufficient fields for triage and trend reporting.

## Validation
- Unit tests for drift detection logic.
- Integration test with controlled parser-version change.
- Query test for drift trend retrieval.

## Deliverables
- Drift event schema/model and persistence logic.
- Version metadata propagation in processing pipeline.
- Automated tests for detection and queryability.
