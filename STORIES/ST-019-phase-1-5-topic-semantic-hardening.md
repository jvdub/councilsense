# Phase 1.5: Topic Semantic Hardening

**Story ID:** ST-019  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** GAP_PLAN §Phase 2, GAP_PLAN §Parity Targets (Topic quality), GAP_PLAN §Gate B, FR-4

## User Story
As a reader, I want notable topics expressed as civic concept phrases so topic labels are meaningful and grounded in meeting outcomes.

## Scope
- Derive phrase-level topics from decisions/actions/claims in existing summarization pipeline.
- Suppress low-information generic tokens and normalize to 3–5 civic concept labels.
- Ensure each emitted topic maps to supporting evidence references.

## Acceptance Criteria
1. Topic extraction emits concept-level civic phrases and suppresses generic-only labels (for example "approved" without civic context).
2. Output normalizes to 3–5 notable topics per meeting when sufficient evidence exists.
3. Every topic in fixture outputs has at least one supporting evidence mapping.
4. Topic semantic thresholds pass on all rubric fixtures under scorecard evaluation.
5. Existing summary/decision/action contracts remain unchanged except additive hardening effects.

## Implementation Tasks
- [ ] Implement phrase-level topic derivation in summarization pipeline using existing artifacts.
- [ ] Implement configurable suppression list for low-information topic tokens.
- [ ] Implement normalization logic for civic-concept topic labels and count bounds.
- [ ] Add evidence-mapping enforcement for each topic.
- [ ] Add unit/integration tests for semantic quality, suppression, and fixture-level thresholds.

## Dependencies
- ST-005
- ST-017
- ST-018

## Definition of Done
- Topic outputs consistently meet semantic quality targets across fixture set.
- Topic-to-evidence mapping is test-enforced.
- Gate B topic checks are ready for report-only and enforced execution.
