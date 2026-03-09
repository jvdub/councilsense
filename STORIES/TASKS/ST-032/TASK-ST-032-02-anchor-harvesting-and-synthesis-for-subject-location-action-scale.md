# Anchor Harvesting and Synthesis for Subject, Location, Action, and Scale

**Task ID:** TASK-ST-032-02  
**Story:** ST-032  
**Bucket:** backend  
**Requirement Links:** ST-032 Acceptance Criteria #1 and #3, FR-4, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §14(10-11)

## Objective

Extend anchor harvesting and synthesis logic so substantive meeting items retain concrete project, place, action, and scale details when supported by source evidence.

## Scope

- Capture named plans, ordinances, projects, zoning districts, parcels, streets, neighborhoods, and comparable subject anchors.
- Capture action-oriented context and material scale details such as units, acres, costs, dates, and vote counts.
- Produce structured relevance candidates from grounded source text for downstream decisioning.
- Out of scope: impact-tag classification and reader API serialization.

## Inputs / Dependencies

- TASK-ST-032-01 structured relevance model.
- Existing specificity anchor harvesting from ST-020.
- Existing compose and claim-evidence assembly behavior from ST-025 and ST-026.

## Implementation Notes

- Prefer deterministic extraction rules over freeform text synthesis.
- Reuse existing evidence pointer and anchor signals where practical.
- Ensure extraction can tolerate partial-source bundles without fabricating subjects or locations.

## Acceptance Criteria

1. Structured extraction captures concrete subject and location anchors for representative zoning, development, infrastructure, and budget fixtures.
2. Action and scale candidates are grounded in source text rather than inferred from topic tokens alone.
3. Extraction remains deterministic across repeated runs with unchanged inputs.
4. Sparse or missing source detail degrades safely without emitting invented anchors.

## Validation

- Run fixture cases containing named plans, districts, and quantitative details.
- Verify extracted anchors map back to evidence-bearing source spans or excerpts.
- Confirm reruns produce stable structured values for unchanged source inputs.

## Deliverables

- Extended anchor harvesting logic for subject, location, action, and scale.
- Fixture examples demonstrating structured candidate capture.
- Determinism notes for repeated-run behavior.