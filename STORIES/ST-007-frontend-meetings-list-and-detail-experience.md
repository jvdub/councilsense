# Frontend Meetings List + Detail Experience

**Story ID:** ST-007  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.5(1-3), FR-4, NFR-2

## User Story
As a resident, I want a clear meetings list and detail page so I can quickly read outcomes with source evidence.

## Scope
- Implement `/meetings` and `/meetings/[meetingId]` UX flows.
- Display summary, key decisions, notable topics, and evidence snippets/links.
- Render `limited_confidence` state clearly.
- Provide loading, error, and empty states.

## Acceptance Criteria
1. Meetings page lists recent meetings for user home city.
2. Meeting detail displays summary, decisions/actions, topics, and evidence references.
3. Limited-confidence meetings show explicit confidence banner/label.
4. UI handles loading/error/empty states without breaking navigation.
5. Notification links containing `meeting_id` deep-link to the correct meeting detail page.

## Implementation Tasks
- [ ] Build meetings list page with pagination/incremental loading.
- [ ] Build meeting detail page sections and confidence rendering.
- [ ] Add robust state handling components (loading, empty, error).
- [ ] Implement URL/deep-link route handling for meeting detail.
- [ ] Add component and e2e smoke tests for core reader flows.

## Dependencies
- ST-001
- ST-006

## Definition of Done
- Reader UI is usable end-to-end from authenticated session to evidence view.
- Confidence labeling behavior matches backend status fields.
- Core reader tests pass in CI.
