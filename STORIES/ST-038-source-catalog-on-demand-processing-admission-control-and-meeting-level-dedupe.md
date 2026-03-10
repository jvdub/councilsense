# Source Catalog: On-Demand Processing Admission Control and Meeting-Level Dedupe

**Story ID:** ST-038  
**Phase:** Phase 5 (Processing orchestration hardening)  
**Requirement Links:** FR-3, FR-4, FR-7, NFR-1, NFR-4

## User Story
As a platform operator, I want on-demand processing requests to dedupe by meeting and respect admission-control limits so residents can request summaries without causing duplicate ingestion or uncontrolled queue growth.

## Scope
- Implement meeting-level active-work dedupe so only one queued/in-progress processing flow exists per discovered meeting.
- Add bounded admission controls for resident-triggered requests, including configurable per-user request ceilings and duplicate-click suppression.
- Reuse existing pipeline lifecycle and retry/audit patterns where possible instead of creating a parallel worker model.
- Ensure transitions from discovered meeting to local meeting/run/publication state remain idempotent.

## Acceptance Criteria
1. When a meeting already has queued or in-progress work, new requests do not create another active processing job.
2. Resident-triggered requests are subject to configurable admission-control limits and return deterministic responses when limits are exceeded.
3. Duplicate clicks or repeated requests for the same meeting resolve to the same active work item until that work reaches a terminal state.
4. Terminal failures can be retried or replayed without creating duplicate artifacts, publications, or active jobs.
5. Integration tests cover active-work dedupe, limit enforcement, and terminal-state re-request behavior.

## Implementation Tasks
- [ ] Define the active-work dedupe key for a discovered meeting using stable source identity.
- [ ] Implement request admission-control checks and duplicate-click suppression semantics.
- [ ] Reuse pipeline lifecycle/retry state to represent queued and in-progress on-demand work.
- [ ] Ensure terminal-state requests can open a new attempt safely while preserving audit history.
- [ ] Add integration coverage for dedupe, limit handling, and idempotent retry/replay behavior.

## Dependencies
- ST-004
- ST-029
- ST-036
- ST-037

## Definition of Done
- On-demand work is deduplicated at the meeting level and bounded by admission controls.
- Existing retry and audit patterns remain authoritative for active and terminal work.
- Operators can reason about queued, in-progress, failed, and retried requests without duplicate side effects.