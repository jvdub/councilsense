# Contract Fixtures for Nominal, Sparse, and Missing-Data Cases

**Task ID:** TASK-ST-033-04  
**Story:** ST-033  
**Bucket:** tests  
**Requirement Links:** ST-033 Acceptance Criteria #3 and #4, FR-4, REQUIREMENTS §13.2 Trust Outcome

## Objective

Build a contract fixture matrix that covers full resident-relevance payloads, sparse structured data, and missing-data scenarios for safe additive behavior.

## Scope

- Add nominal fixtures with full structured relevance coverage.
- Add sparse fixtures where only some resident-relevance fields are available.
- Add legacy or unsupported fixtures where resident-relevance fields are omitted entirely.
- Out of scope: latency checks and frontend rendering tests.

## Inputs / Dependencies

- TASK-ST-033-03 resident-relevance serializer behavior.
- Existing contract fixture patterns from ST-018, ST-022, and ST-027.

## Implementation Notes

- Keep fixtures explicit about omission vs empty collection behavior.
- Ensure examples are realistic for zoning, development, infrastructure, or budget items.
- Prefer snapshot-like stability for fixture bundles.

## Acceptance Criteria

1. Fixtures cover nominal, sparse, and missing-data resident-relevance cases.
2. Omission semantics are verified explicitly for legacy or unsupported publications.
3. Deterministic ordering of `impact_tags` and linked evidence is asserted where present.
4. Fixture bundle remains stable across reruns unless contract changes intentionally.

## Validation

- Run contract tests against the new fixture bundle.
- Verify omission semantics differ correctly from empty array semantics.
- Confirm fixture bundle is stable under repeated serialization.

## Deliverables

- Resident-relevance contract fixture bundle.
- Contract tests for presence, omission, and deterministic ordering.
- Notes documenting sparse-data expectations.