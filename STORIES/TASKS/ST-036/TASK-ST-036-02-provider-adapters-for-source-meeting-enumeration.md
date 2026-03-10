# Provider Adapters for Source Meeting Enumeration

**Task ID:** TASK-ST-036-02  
**Story:** ST-036  
**Bucket:** backend  
**Requirement Links:** ST-036 Scope (source sync paths), ST-036 Acceptance Criteria #3 and #5, FR-3, FR-7

## Objective

Implement provider adapters that enumerate available source meetings so the platform can build a discovered-meetings catalog instead of selecting only a single latest candidate.

## Scope

- Define an extensible enumeration interface for supported source providers.
- Implement the pilot enumeration path for CivicClerk meeting discovery.
- Normalize provider payloads into the discovered-meeting identity and metadata contract.
- Out of scope: persistence/reconciliation, reader API behavior, and request queue admission control.

## Inputs / Dependencies

- TASK-ST-036-01 discovered-meeting schema and source-identity contract.
- Existing CivicClerk fetch and event-selection logic.
- ST-003 source registry metadata for enabled provider/source configuration.

## Implementation Notes

- Reuse existing provider-specific parsing where practical instead of duplicating fetch logic.
- Keep enumeration separate from latest-selection heuristics.
- Design the interface so future providers can plug in without reshaping the discovered-meeting contract.

## Acceptance Criteria

1. The pilot provider adapter returns a stable list of discovered meeting candidates with normalized metadata. (supports ST-036 AC #3)
2. Enumeration logic is separated from persistence and can be reused by scheduled sync paths.
3. Provider parsing behavior is deterministic for repeated source payloads. (supports ST-036 AC #5)

## Validation

- Unit tests for provider enumeration and normalization.
- Fixture coverage for nominal, sparse, and reordered source payloads.
- Verify source identities remain stable across repeated enumerations of the same feed.

## Deliverables

- Provider enumeration interface and pilot implementation.
- Normalization logic from provider payloads to discovered-meeting contract.
- Unit tests for provider parsing and stability.
