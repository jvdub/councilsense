# Source Health + Manual Review Baseline

**Story ID:** ST-010  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** FR-7, NFR-4, Phase 1 baseline (§9)

## User Story
As an operator, I want source freshness and low-confidence runs flagged so I can keep ingestion reliable and triage questionable outputs.

## Scope
- Record source health state and last-success timestamps per city source.
- Record parser/source version used in processing runs.
- Route low-confidence extraction runs to manual-review-needed state.

## Acceptance Criteria
1. Each city source exposes `health_status` and `last_success_at` fields.
2. Processing runs persist parser/source version metadata for reproducibility.
3. Low extraction confidence is persisted and flagged for manual review.
4. Reader-visible output indicates limited confidence when applicable.
5. Source failures are isolated and visible without global pipeline interruption.

## Implementation Tasks
- [ ] Persist and update source health metrics during ingest attempts.
- [ ] Capture parser/source version metadata in processing runs.
- [ ] Add confidence threshold policy to mark `manual_review_needed`.
- [ ] Provide basic operator query/view for stale or failing sources.
- [ ] Add tests for confidence threshold transitions and source health updates.

## Dependencies
- ST-003
- ST-004
- ST-005

## Definition of Done
- Baseline source health data is available for pilot operations.
- Manual review candidates are clearly identifiable.
- Reproducibility metadata is persisted for each run.
