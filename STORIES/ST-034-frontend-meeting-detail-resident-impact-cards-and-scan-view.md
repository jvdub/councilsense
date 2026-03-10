# Resident Relevance: Meeting Detail Impact Cards and Scan View

**Story ID:** ST-034  
**Phase:** Phase 4 (Resident relevance + explainability)  
**Requirement Links:** FR-4, §12.3 Web App, §13.1 Resident Outcome, §13.2 Trust Outcome, §13.5 Clarity Outcome, §14(3,10)

## User Story

As a resident, I want the meeting detail page to show concise cards for what changed, where it applies, and why it may matter so I can scan relevance before reading the full summary.

## Scope

- Add a resident-oriented scan layer to meeting detail that surfaces structured subject, location, action, scale, and impact tags ahead of longer-form sections.
- Present major items as concise cards with evidence-backed labels and clear empty states.
- Preserve the current baseline detail rendering when additive resident-relevance fields are absent or feature-gated off.
- Keep evidence references and existing decisions/actions sections accessible from the scan view rather than replacing them.

## Acceptance Criteria

1. When resident-relevance fields are present and enabled, meeting detail renders item cards summarizing what, where, action, and scale for substantive items.
2. Cards display impact tags only when the backing API fields are present and valid.
3. Residents can move from a card to supporting detail or evidence without losing access to the existing baseline sections.
4. Flag-off or missing-data behavior falls back to the current baseline meeting detail experience.
5. Frontend tests cover additive rendering, fallback states, empty states, and accessibility of the scan layer.

## Implementation Tasks

- [ ] Define the resident scan-card component model and feature-flag behavior.
- [ ] Bind additive resident-relevance fields into meeting detail sections without disturbing baseline layout order.
- [ ] Add evidence and navigation affordances from scan cards into existing detailed sections.
- [ ] Implement empty and sparse states for meetings with partial resident-relevance coverage.
- [ ] Add component and page verification tests for baseline and additive modes.

## Dependencies

- ST-007
- ST-028
- ST-033

## Definition of Done

- Meeting detail offers a faster resident relevance scan path when structured fields are available.
- Baseline meeting detail remains stable when the new fields are unavailable or disabled.
- Tests validate both readability and fallback behavior.
