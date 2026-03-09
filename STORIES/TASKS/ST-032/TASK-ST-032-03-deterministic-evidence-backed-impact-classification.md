# Deterministic Evidence-Backed Impact Classification

**Task ID:** TASK-ST-032-03  
**Story:** ST-032  
**Bucket:** backend  
**Requirement Links:** ST-032 Acceptance Criteria #2 and #4, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Implement deterministic resident-impact tag classification grounded in claim-evidence paths so summaries can explain why an item may matter to residents.

## Scope

- Define the approved impact-tag set for resident-facing classification.
- Classify tags from grounded structured relevance and claim text.
- Ensure `impact_tags` ordering and inclusion are deterministic across reruns.
- Out of scope: UI presentation and follow-up prompt generation.

## Inputs / Dependencies

- TASK-ST-032-01 structured relevance model.
- Existing claim and evidence linkage behavior from ST-005 and ST-026.

## Implementation Notes

- Keep the tag set bounded and explainable.
- Require evidence-backed support for each assigned tag.
- Avoid broad or speculative tags when the supporting evidence is weak.

## Acceptance Criteria

1. Approved impact tags are defined and mapped to grounded evidence-bearing conditions.
2. Classification results are deterministic across reruns for unchanged inputs.
3. Every emitted impact tag can be traced to structured relevance values or claim-evidence support.
4. Unsupported tags are omitted rather than weakly inferred.

## Validation

- Run representative fixtures for housing, traffic, utilities, parks, fees, and land-use topics.
- Verify repeated runs preserve tag set and ordering.
- Confirm no tag is emitted without a valid grounded support path.

## Deliverables

- Impact-tag taxonomy and classification rules.
- Deterministic ordering behavior for `impact_tags`.
- Validation evidence for evidence-backed tag assignment.