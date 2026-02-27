# Align profile preference schema fields

**Task ID:** TASK-ST-002-01  
**Story:** ST-002  
**Bucket:** data  
**Requirement Links:** FR-2, FR-5(4)

## Objective
Ensure persisted profile model supports city, notification enabled flag, and pause window fields needed by ST-002.

## Scope
- Add/verify required profile preference fields and constraints.
- Add migration if schema is incomplete.
- Out of scope: API handlers and UI behavior.

## Inputs / Dependencies
- ST-001 profile bootstrap baseline
- Current DB schema and migration history

## Implementation Notes
- Target user/profile table schema and migration files.
- Keep nullable/required semantics aligned with story behavior.

## Acceptance Criteria
1. Schema contains fields needed for city + notification pause controls.
2. Migration applies cleanly in local development database.
3. Existing profile records remain readable after migration.

## Validation
- Run migration apply/status checks.
- Run schema-level tests or lightweight repository checks.

## Deliverables
- Migration(s) and model updates for profile preferences.
