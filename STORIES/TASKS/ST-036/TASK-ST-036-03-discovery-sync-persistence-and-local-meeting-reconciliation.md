# Discovery Sync Persistence and Local-Meeting Reconciliation

**Task ID:** TASK-ST-036-03  
**Story:** ST-036  
**Bucket:** backend  
**Requirement Links:** ST-036 Scope (sync baseline and reconciliation), ST-036 Acceptance Criteria #2 and #4, FR-6, NFR-1

## Objective

Persist discovered meetings from enumeration results and reconcile them to existing local `meetings` rows when a stable source identity is already known.

## Scope

- Implement discovery sync writes for new and existing discovered-meeting rows.
- Refresh mutable metadata on reruns without creating duplicate discovered-meeting rows.
- Link discovered meetings to existing local `meetings` rows when a stable source identity match is available.
- Out of scope: dedupe policy diagnostics, reader query contract, and on-demand request queue behavior.

## Inputs / Dependencies

- TASK-ST-036-01 schema and source-identity contract.
- TASK-ST-036-02 provider enumeration output.
- Existing `meetings` write/read model and ingest metadata lineage.

## Implementation Notes

- Keep reconciliation additive and non-blocking when no local meeting match exists.
- Preserve sync timestamps so later freshness monitoring is possible.
- Avoid coupling sync persistence to downstream processing state.

## Acceptance Criteria

1. Discovery sync inserts newly discovered meetings and updates mutable metadata on rerun without duplicates. (ST-036 AC #2)
2. Existing local meetings can be linked to discovered meetings when stable source identity is known. (ST-036 AC #4)
3. Sync behavior remains safe when some discovered items cannot yet be reconciled to local meetings.

## Validation

- Integration tests for first sync, repeated sync, and metadata refresh.
- Reconciliation tests for matched and unmatched local meetings.
- Verify unmatched discovered meetings remain available for later processing.

## Deliverables

- Discovery sync persistence path.
- Local-meeting reconciliation logic.
- Integration coverage for insert/update/reconcile flows.
