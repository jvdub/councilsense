# Phase 1.5: Specificity + Evidence Locator Precision Hardening

**Story ID:** ST-020  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** GAP_PLAN §Phase 3, GAP_PLAN §Parity Targets (Specificity, Grounding, Evidence precision), GAP_PLAN §Gate B, FR-4

## User Story

As a reader, I want quantitative specifics and precise evidence locators retained in summaries so I can verify important claims quickly.

## Scope

- Harvest quantitative anchors (units, acres, dates, counts, named entities) from parsed meeting content.
- Enforce anchor carry-through into summary or decisions/actions when anchors are present in source.
- Build deterministic evidence projection with dedupe/ranking and improve locator precision where parser supports subsection/offset.

## Acceptance Criteria

1. For fixtures containing quantitative anchors, at least one anchor appears in summary or key decisions/actions.
2. Grounding coverage remains 100% for key decisions/actions (each has at least one evidence pointer).
3. `evidence_references` projection is deterministic across reruns and deduplicates equivalent pointers.
4. Majority of evidence pointers are finer than file-level when parser-provided subsection/offset data is available.
5. Specificity and evidence thresholds pass on all rubric fixtures without degrading existing publish reliability.

## Implementation Tasks

- [ ] Implement anchor harvesting for quantitative and entity-like specificity signals.
- [ ] Implement carry-through checks/enforcement in summarization output assembly.
- [ ] Implement deterministic evidence dedupe/ranking projection for reader payload and scorecard use.
- [ ] Implement locator precision preference for subsection/offset pointers when technically available.
- [ ] Add unit/integration tests for anchor retention, grounding coverage, dedupe determinism, and locator precision.

## Dependencies

- ST-017
- ST-018
- ST-019

## Definition of Done

- Specificity retention and evidence-precision parity targets pass on fixture scorecards.
- Decision/action grounding remains complete and deterministic.
- Locator precision behavior is measurable and validated in tests.
