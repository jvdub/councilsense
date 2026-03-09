# Resident Relevance: Structured Subject, Location, and Impact Extraction

**Story ID:** ST-032  
**Phase:** Phase 4 (Resident relevance + explainability)  
**Requirement Links:** FR-4, §12.2 Summarization & Relevance Service, §13.1 Resident Outcome, §13.2 Trust Outcome, §13.5 Clarity Outcome, §14(10-11)

## User Story
As a resident, I want summaries to retain the specific project, place, and likely impact of a council action so I can tell quickly whether it affects me.

## Scope
- Extend summarization output assembly to capture structured subject anchors for substantive meeting items, including project or ordinance name, place context, action taken, and scale details when present.
- Classify resident-facing impact tags such as housing, traffic, utilities, parks, public safety, taxes or fees, and land use when grounded in source evidence.
- Enforce carry-through so generic phrases like "approved a development plan" are upgraded to concrete phrasing when source evidence supports a more specific subject.
- Preserve limited-confidence behavior when the source does not support a concrete subject, location, or impact statement.

## Acceptance Criteria
1. For development, zoning, infrastructure, and budget-related fixtures, summary or key decisions/actions include at least one concrete subject anchor when the source names a project, ordinance, district, street, parcel, or comparable identifier.
2. Structured extraction captures additive fields for `subject`, `location`, `action`, `scale`, and `impact_tags` when grounded evidence exists, and omits them safely when it does not.
3. Generic decision text is not emitted when a more specific, evidence-backed subject phrase is available from the same source bundle.
4. Impact tags are deterministic across reruns for unchanged source inputs and are backed by at least one claim-evidence path.
5. When specificity is unavailable or conflicting, publication remains explicit about uncertainty rather than inferring a concrete subject or impact.

## Implementation Tasks
- [ ] Define internal structured relevance fields for subject, location, action, scale, and impact tags.
- [ ] Extend anchor harvesting and synthesis logic to capture named plans, ordinances, zoning districts, streets, parcels, neighborhoods, and material scale details.
- [ ] Implement carry-through rules that prefer concrete subject phrasing over generic action-only summaries.
- [ ] Implement deterministic resident-impact classification grounded in evidence-backed claim text.
- [ ] Add fixture and scorecard coverage for subject specificity, location carry-through, and impact-tag determinism.

## Dependencies
- ST-020
- ST-025
- ST-026

## Definition of Done
- Summarization outputs preserve resident-relevant subject and location detail when source evidence supports it.
- Impact tags are evidence-backed, deterministic, and measurable in tests or scorecards.
- Limited-confidence behavior remains intact for low-specificity or conflicting source material.