# Source Catalog: Frontend Meeting Explorer and On-Demand Processing UX

**Story ID:** ST-039  
**Phase:** Phase 5 (Frontend reader experience)  
**Requirement Links:** FR-4, FR-6, NFR-2

## User Story
As a resident, I want the meetings page to show all available source meetings with clear processing states and a request-summary action so I can get summaries for the meeting I actually care about.

## Scope
- Evolve the meetings page from a processed-meetings list into a paginated meeting explorer backed by the discovered-meetings API.
- Render user-visible states for unprocessed, queued, processing, processed, and failed meetings.
- Provide a request-processing action for eligible meetings and surface duplicate-request or limit responses clearly.
- Preserve deep-linking, pagination, empty/error states, and processed meeting detail navigation.

## Acceptance Criteria
1. Meetings page displays discovered meetings for the resident's home city with pagination.
2. Each meeting tile shows a clear processing state and action affordance appropriate to that state.
3. Requesting processing updates the tile state without requiring the user to understand backend queue details.
4. Processed meetings still link to meeting detail, and active work states surface progress messaging rather than broken links.
5. Component/page tests cover state rendering, request action flows, duplicate-active-request messaging, and error handling.

## Implementation Tasks
- [ ] Update meetings page data model and API client usage for discovered-meeting pagination.
- [ ] Design tile variants and CTA behavior for unprocessed, queued, processing, processed, and failed states.
- [ ] Implement request-processing interaction and user messaging for accepted, duplicate-active, and limited responses.
- [ ] Preserve deep-link handling and processed-detail navigation semantics.
- [ ] Add component/page tests for pagination, tile states, and request action outcomes.

## Dependencies
- ST-007
- ST-037
- ST-038

## Definition of Done
- Residents can discover and request summaries for specific source meetings from the main meetings page.
- Processing-state UX is clear and resilient across duplicate requests, limits, and failures.
- Frontend tests validate the primary meeting-explorer flows end to end at the page/component level.