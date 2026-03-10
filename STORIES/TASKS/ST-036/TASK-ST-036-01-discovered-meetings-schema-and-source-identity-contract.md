# Discovered-Meetings Schema and Source-Identity Contract

**Task ID:** TASK-ST-036-01  
**Story:** ST-036  
**Bucket:** data  
**Requirement Links:** ST-036 Scope (discovered-meetings registry), ST-036 Acceptance Criteria #1 and #3, FR-3, FR-6, NFR-4

## Objective

Define the additive schema and stable source-identity contract for discovered meetings so source sync can persist a canonical row per source meeting.

## Scope

- Design additive tables, indexes, and uniqueness constraints for discovered source meetings.
- Define the stable source-identity fields required for provider-specific dedupe and reconciliation.
- Define the minimum normalized metadata contract for title, meeting date, body name, source URL, and sync timestamps.
- Out of scope: provider enumeration logic, reader API payload shape, and request queue semantics.

## Inputs / Dependencies

- ST-003 city/source configuration and source registry assumptions.
- ST-023 source-scoped identity and dedupe conventions.
- Existing `meetings` and processing lifecycle schema.

## Implementation Notes

- Keep the schema additive and non-destructive.
- Favor a provider-stable source identity over title/date matching.
- Include linkage fields that allow later reconciliation to local `meetings` rows without forcing immediate backfill.

## Acceptance Criteria

1. A discovered-meeting row can be uniquely identified by stable source identity within city/source scope. (ST-036 AC #1)
2. The schema captures all metadata required to render a meeting tile before local processing exists. (ST-036 AC #3)
3. The migration plan preserves compatibility with existing `meetings` and processing-run tables.

## Validation

- Review migration and uniqueness rules for additive-only behavior.
- Add schema-level tests for uniqueness and referential integrity where appropriate.
- Confirm the model supports reconciliation without relying on title/date heuristics alone.

## Deliverables

- Additive discovered-meetings schema and index plan.
- Stable source-identity contract documentation in code/tests.
- Schema validation coverage for uniqueness and linkage assumptions.
