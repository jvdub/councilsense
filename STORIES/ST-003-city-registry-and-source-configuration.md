# City Registry + Source Configuration

**Story ID:** ST-003  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.2, FR-2, FR-3, FR-7, NFR-5

## User Story
As an operations/admin maintainer, I want city and source configuration to be city-agnostic so the system can run one pilot city now and expand later without redesign.

## Scope
- Define and seed configured city list (pilot city enabled by default).
- Define city source registry (source URL/type, parser version, enabled state).
- Ensure meetings and runs are always city-linked.

## Acceptance Criteria
1. Pilot city is enabled by default; data model supports multiple cities.
2. Source config exists per city with parser/source metadata fields.
3. Meetings are stored with mandatory city identifier.
4. Scheduler/input selection can target configured cities even with zero subscribers.
5. City validation for user profile references uses configured city registry.

## Implementation Tasks
- [ ] Create/verify migrations for `cities` and `city_sources` with required constraints.
- [ ] Add seed scripts for pilot city and initial source configuration.
- [ ] Implement repository/service layer for configured-city selection.
- [ ] Add city linkage checks in meeting creation/upsert logic.
- [ ] Add tests for city validation and zero-subscriber ingestion eligibility.

## Dependencies
- ST-001

## Definition of Done
- City and source configuration is fully data-driven and environment-configurable.
- Pilot city can be processed without any user subscriptions.
- Tests confirm city linkage and registry validation behavior.
