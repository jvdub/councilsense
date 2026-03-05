# Agenda Plan: Authority-Aware Multi-Document Compose and Limited-Confidence Policy

**Story ID:** ST-025  
**Phase:** Phase 1–2 (Summarization continuity and authority policy)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §5 Phase 1 — MVP multi-source ingestion and publish continuity (Weeks 2–3), AGENDA_PLAN §8 Risks and mitigations

## User Story
As a resident, I want outcomes grounded in the authoritative source with clear confidence labels so I can trust published meeting summaries even when source coverage is partial.

## Scope
- Build structured multi-document compose context from AGENDA_PLAN section "Target architecture (summarization)".
- Enforce authority policy (minutes authoritative for final decisions/actions; agenda/packet supporting) from AGENDA_PLAN section "Target architecture".
- Implement limited-confidence publication with explicit reason codes for missing/weak/conflicting sources from AGENDA_PLAN sections "Phase 1" and "Risks and mitigations".

## Acceptance Criteria
1. Compose step includes available canonical documents in deterministic source order.
2. Decisions/actions prefer minutes-aligned evidence when minutes are available.
3. Unresolved conflicts or weak precision trigger `limited_confidence` with explicit reason codes.
4. Publish continuity is preserved; partial-source meetings still publish with confidence policy.
5. Tests cover source conflict handling and confidence downgrade logic.

## Implementation Tasks
- [ ] Implement multi-document compose assembly for summarize input.
- [ ] Implement authority alignment decisioning for outcomes extraction.
- [ ] Implement confidence reason-code taxonomy and publish-state wiring.
- [ ] Add conflict fixtures (minutes vs agenda/packet disagreement) and expected outputs.
- [ ] Add tests for deterministic compose and limited-confidence transitions.

## Dependencies
- ST-005
- ST-023
- ST-024

## Definition of Done
- Summarization uses multi-document context with explicit authority policy.
- Limited-confidence behavior is transparent, deterministic, and test-validated.
- Publish path remains resilient under partial-source conditions.
