# Source Conflict and Partial-Coverage Fixtures

**Task ID:** TASK-ST-025-04  
**Story:** ST-025  
**Bucket:** tests  
**Requirement Links:** ST-025 Acceptance Criteria #3 and #5, AGENDA_PLAN §8 Risks and mitigations (source conflict + parser drift), AGENDA_PLAN §5 Phase 1

## Objective
Create fixture sets that model authoritative conflicts, partial-source coverage, and weak-precision conditions for deterministic confidence-policy testing.

## Scope
- Add fixtures for minutes vs agenda/packet disagreement on decisions/actions.
- Add fixtures for missing-minutes and missing-supplemental-source coverage patterns.
- Add fixtures for weak precision metadata scenarios triggering limited confidence.
- Out of scope: production parser changes and UI rendering behavior.

## Inputs / Dependencies
- TASK-ST-025-01 compose input schema.
- ST-024 canonical document/artifact/span persistence fixture primitives.
- Existing backend test fixture harness and golden-output conventions.

## Implementation Notes
- Each fixture should declare expected compose ordering, authority outcome, and confidence reason codes.
- Keep fixture naming aligned to policy scenario intent for maintainability.
- Ensure fixtures are reusable across unit and integration policy suites.

## Acceptance Criteria
1. Conflict fixtures cover minutes-authoritative and unresolved-conflict branches.
2. Partial-coverage fixtures cover publish-continuity paths under limited confidence.
3. Weak-precision fixtures validate reason-code emission and downgrade behavior.
4. Fixture catalog documents expected outcomes for deterministic assertions.

## Validation
- Execute fixture-driven policy tests and verify expected outputs.
- Confirm fixture coverage spans full-source, partial-source, and conflict scenarios.
- Review fixture determinism by rerunning test selection multiple times.

## Deliverables
- Fixture dataset and scenario manifest.
- Expected-output mapping for authority and confidence outcomes.
- Reusable fixture helpers for compose and publish policy tests.
