# v1 Contract Specification and Approval Fixtures

**Task ID:** TASK-ST-022-01  
**Story:** ST-022  
**Bucket:** docs  
**Requirement Links:** ST-022 Scope (v1 payloads), ST-022 Acceptance Criteria #1, AGENDA_PLAN §4

## Objective

Freeze a versioned v1 API contract for `planned`, `outcomes`, `planned_outcome_mismatches`, and `evidence_references_v2`, with fixtures that can be approved by backend and frontend owners.

## Scope

- Author canonical JSON schema examples for all v1 additive payload blocks.
- Define required vs optional fields and nullability rules per block.
- Produce contract fixtures for nominal, partial-source, and limited-confidence publication cases.
- Out of scope: implementation of API handlers, persistence logic, and compatibility shim transforms.

## Inputs / Dependencies

- ST-022 story scope and acceptance criteria.
- AGENDA_PLAN v1-first contract guidance.
- Consumer expectations from meeting reader API and frontend detail view.

## Implementation Notes

- Store fixtures in a location consumable by backend and frontend tests.
- Include explicit source-kind evidence examples (minutes, agenda, packet) and precision metadata.
- Require sign-off checklist fields for backend, frontend, and product/platform owner.

## Acceptance Criteria

1. v1 contract spec documents all four target payload shapes with stable field semantics. (ST-022 AC #1)
2. Fixture set includes at least one valid example per payload block and one limited-confidence case. (ST-022 AC #1)
3. Contract package includes approval status and reviewers. (ST-022 AC #1)

## Validation

- Validate fixture JSON against the v1 schema definitions.
- Review fixture compatibility with existing meeting detail contract tests.
- Capture reviewer sign-off outcomes.

## Deliverables

- Versioned v1 contract specification.
- Approved fixture bundle for `planned`, `outcomes`, `planned_outcome_mismatches`, and `evidence_references_v2`.
- Sign-off checklist artifact.
