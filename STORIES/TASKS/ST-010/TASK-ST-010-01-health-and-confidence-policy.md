# Health and Confidence Policy

**Task ID:** TASK-ST-010-01  
**Story:** ST-010  
**Bucket:** docs  
**Requirement Links:** FR-7, NFR-4, Phase 1 baseline

## Objective
Define the minimal policy for source health states and confidence thresholds that drive manual review routing.

## Scope
- In scope:
  - Health status enum and transition triggers.
  - Confidence threshold rule for manual_review_needed.
  - Reader-facing low-confidence indicator rule.
- Out of scope:
  - Database and API implementation.

## Inputs / Dependencies
- ST-003 source registry model
- ST-005 extraction confidence output

## Implementation Notes
- Keep thresholds configurable via environment settings.
- Define behavior for missing confidence signal.
- Include examples for pass, warn, and manual-review outcomes.

## Acceptance Criteria
1. Policy document defines exact status values and transitions.
2. Confidence rule is deterministic and environment-configurable.
3. Operator and reader implications are explicitly stated.

## Validation
- Policy review with backend and product stakeholders.
- Add policy unit tests for threshold decision helper.

## Deliverables
- Policy spec document.
- Threshold helper contract with tests.
