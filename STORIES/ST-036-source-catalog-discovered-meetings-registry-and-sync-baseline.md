# Source Catalog: Discovered Meetings Registry and Sync Baseline

**Story ID:** ST-036  
**Phase:** Phase 5 (Source catalog foundation)  
**Requirement Links:** FR-3, FR-6, FR-7, NFR-1, NFR-4

## User Story
As a resident, I want CouncilSense to show meetings the source website already exposes so I can request summaries for a specific meeting instead of relying on a single latest-meeting heuristic.

## Scope
- Add an additive discovered-meetings registry that stores stable source meeting identity, city/source linkage, meeting metadata, and sync timestamps.
- Implement source sync paths that enumerate source meetings from supported providers, with CivicClerk as the initial baseline.
- Persist enough metadata to reconcile discovered source meetings with existing local `meetings` rows and downstream processing runs.
- Support dedupe of the same source meeting across repeated discovery syncs.

## Acceptance Criteria
1. Discovery sync persists one canonical discovered-meeting row per stable source meeting identity.
2. Re-running discovery for the same source window updates metadata without creating duplicate discovered-meeting rows.
3. Discovered meetings retain enough metadata to render title, meeting date, body name, source URL, and provider-specific source identity.
4. Existing processed meetings can be linked back to their discovered source meeting when a stable source identity is available.
5. Tests cover discovery sync idempotency, stable identity mapping, and provider-specific parsing for the pilot path.

## Implementation Tasks
- [ ] Design additive schema for discovered source meetings and source-identity linkage.
- [ ] Implement provider adapters that enumerate available meetings instead of only selecting the latest candidate.
- [ ] Persist provider-specific stable source identities and normalized meeting metadata.
- [ ] Reconcile discovered meetings with existing `meetings` records where a matching source identity is already known.
- [ ] Add unit/integration coverage for discovery reruns, dedupe, and metadata refresh behavior.

## Dependencies
- ST-003
- ST-004
- ST-023

## Definition of Done
- Source discovery produces a durable, deduplicated meeting catalog per city/source.
- Discovery reruns are idempotent and safe for scheduled refreshes.
- The registry provides the metadata required for API and frontend pagination work.