# Evidence-Grounded Summarization + Quality Gate

**Story ID:** ST-005  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** MVP §4.3(2-4), FR-4, FR-7(3), NFR-4, NFR-7

## User Story
As a reader, I want meeting summaries and claims to be evidence-grounded so I can trust what I read.

## Scope
- Generate summary, key decisions/actions, and notable topics.
- Persist claim-level evidence schema (`artifact_id`, section/offset, excerpt).
- Apply quality gate to publish `processed` or `limited_confidence`.
- Persist provenance append-only after publish.

## Acceptance Criteria
1. Published meeting output includes summary, key decisions, and notable topics.
2. Key claims include at least one valid evidence citation/snippet where source evidence is available.
3. If evidence is weak/absent, output is labeled `limited_confidence` rather than overstated certainty.
4. Citation data includes `artifact_id`, section/offset reference, and excerpt, and is retrievable via reader APIs.
5. Published provenance records are immutable append-only.

## Implementation Tasks
- [ ] Implement summarization output contract and persistence model.
- [ ] Implement evidence extraction/attachment in required schema.
- [ ] Implement quality-gate evaluator and publish-state decisioning.
- [ ] Add append-only protections for published summary/evidence records.
- [ ] Add tests for evidence schema validity and limited-confidence path.

## Dependencies
- ST-004

## Definition of Done
- Publishing path enforces evidence-aware quality decisions.
- Reader-facing data includes retrievable evidence pointers.
- Immutability and quality gate behavior are covered by tests.
