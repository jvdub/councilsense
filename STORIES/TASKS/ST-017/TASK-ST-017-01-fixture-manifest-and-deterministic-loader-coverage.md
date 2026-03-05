# Fixture Manifest and Deterministic Loader Coverage

**Task ID:** TASK-ST-017-01  
**Story:** ST-017  
**Bucket:** tests  
**Requirement Links:** GAP_PLAN §Fixture + Scorecard, ST-017 Acceptance Criteria #1 and #5

## Objective
Define and validate a fixed fixture set that includes Eagle Mountain (2024-12-03) plus two structurally different meetings, loaded through deterministic test paths.

## Scope
- Define fixture manifest entries for required meeting set.
- Add deterministic loader checks for fixture ordering and stable identifiers.
- Confirm fixtures are runnable through the existing local pipeline path.
- Out of scope: parity scoring logic and baseline comparison reporting.

## Inputs / Dependencies
- ST-012 local-first runtime conventions.
- Existing meeting fixture assets and metadata.

## Implementation Notes
- Keep fixture selection explicit with city ID, meeting date/time, and source locator.
- Fail fast when required fixtures are missing or duplicated in the manifest.
- Ensure deterministic iteration order for all fixture consumers.

## Acceptance Criteria
1. Fixture manifest includes Eagle Mountain 2024-12-03 and two structurally different meetings.
2. Deterministic loader tests assert stable order and IDs across repeated runs.
3. Fixture set runs via current local pipeline path without introducing runtime behavior changes.
4. Missing fixture entries produce clear test failures.

## Validation
- Run fixture-loader unit/integration tests for deterministic ordering.
- Run local pipeline smoke path against the fixture set.

## Deliverables
- Fixture manifest updates with required meeting coverage.
- Deterministic loader test coverage and failure diagnostics.
- Validation notes confirming local pipeline path compatibility.
