# Seed pilot city and initial source configuration

**Task ID:** TASK-ST-003-02  
**Story:** ST-003  
**Bucket:** data  
**Requirement Links:** MVP §4.2, FR-3

## Objective
Provide deterministic seed data for pilot city and its initial source registry entry.

## Scope
- Add seed records for pilot city.
- Add seed records for at least one city source with parser/source metadata.
- Out of scope: admin UI for editing registry data.

## Inputs / Dependencies
- TASK-ST-003-01

## Implementation Notes
- Target seed scripts or bootstrap initialization path.
- Keep seed idempotent for repeated local/dev runs.

## Acceptance Criteria
1. Fresh environment has pilot city enabled by default.
2. Pilot city has at least one enabled source config entry.
3. Re-running seed does not create duplicate conflicting records.

## Validation
- Run seed command twice and verify stable record count/state.
- Query registry records via repository or DB check script.

## Deliverables
- Seed script updates and seed execution notes.
