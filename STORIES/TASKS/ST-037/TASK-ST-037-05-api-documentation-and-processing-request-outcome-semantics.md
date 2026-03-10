# API Documentation and Processing-Request Outcome Semantics

**Task ID:** TASK-ST-037-05  
**Story:** ST-037  
**Bucket:** docs  
**Requirement Links:** ST-037 Acceptance Criteria #3 and #5, FR-4, FR-6, NFR-4

## Objective

Document the discovered-meetings reader contract and processing-request outcomes so implementers and operators share the same semantics for create-vs-return-existing behavior.

## Scope

- Document list payload semantics for discovered-meeting and processing-status fields.
- Document processing-request outcome meanings for new, existing-active, and error paths.
- Record any explicit non-goals or deferred policy decisions that belong to ST-038.
- Out of scope: frontend copy, runbook details for operator replay, and schema migration implementation.

## Inputs / Dependencies

- TASK-ST-037-03 processing-request endpoint semantics.
- TASK-ST-037-04 contract fixtures and tests.
- Existing API documentation conventions in repo docs and stories.

## Implementation Notes

- Keep language resident-facing where the UI depends on it, but implementation-precise for engineers.
- Separate contract semantics from backend policy internals.
- Capture deferred admission-control details as explicit follow-ons rather than silent assumptions.

## Acceptance Criteria

1. Documentation clearly defines discovered-meeting list and request outcome semantics. (supports ST-037 AC #5)
2. Documentation distinguishes existing-active-request behavior from newly queued work. (supports ST-037 AC #3)
3. Deferred policy decisions are explicitly pointed to ST-038 rather than left implicit.

## Validation

- Cross-check docs against contract fixtures and integration tests.
- Review terminology for consistency with backend and frontend task consumers.

## Deliverables

- API semantics documentation for discovered meetings and processing requests.
- Outcome mapping notes for downstream frontend integration.
- Explicit handoff notes to ST-038 for admission-control hardening.
