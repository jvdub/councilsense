# Source Catalog: Reader API and Queue-or-Return Processing Request Contract

**Story ID:** ST-037  
**Phase:** Phase 5 (API contract and reader expansion)  
**Requirement Links:** FR-4, FR-6, NFR-2, NFR-4

## User Story
As a resident, I want the meetings list API to include discovered-but-unprocessed meetings and give me a safe way to request processing for one of them so the app can return the existing request when work is already underway.

## Scope
- Extend the city meetings reader contract to page through discovered meetings, not only locally processed meeting rows.
- Add additive status fields that distinguish discovered, queued, processing, processed, and failed states.
- Define an authenticated processing-request endpoint that either creates work or returns the existing active work item for the same meeting.
- Preserve city scoping and resident access controls for both listing and processing-request operations.

## Acceptance Criteria
1. City meetings list can page through discovered meetings whether or not a local summary exists.
2. List payload exposes a stable status model that distinguishes unprocessed from active and completed work.
3. Processing-request endpoint is idempotent for the same source meeting and returns the existing active request when one already exists.
4. Reader and processing-request endpoints enforce home-city scoping from the authenticated user profile.
5. Contract tests cover pagination, status projection, duplicate request behavior, and scope enforcement.

## Implementation Tasks
- [ ] Define additive API payload fields for discovered meeting metadata and user-visible processing state.
- [ ] Implement city-scoped meetings list query over discovered-meeting and local-meeting projections.
- [ ] Implement authenticated queue-or-return processing-request endpoint for a discovered meeting.
- [ ] Add contract and integration tests for pagination, idempotent request behavior, and city scoping.
- [ ] Document response semantics for existing-active-request vs newly-queued-request outcomes.

## Dependencies
- ST-006
- ST-036

## Definition of Done
- Residents can browse discovered meetings through the primary reader API.
- API consumers can request processing without creating duplicate active work for the same meeting.
- Contract coverage freezes the additive status and request semantics for frontend work.