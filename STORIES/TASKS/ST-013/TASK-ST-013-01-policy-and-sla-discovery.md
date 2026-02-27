# Governance Policy Baseline and SLA Discovery

**Task ID:** TASK-ST-013-01  
**Story:** ST-013  
**Bucket:** docs  
**Requirement Links:** NFR-3, NFR-7, Requirements §7

## Objective
Define approved retention defaults, deletion SLA, export scope, and immutable-provenance governance rules for implementation.

## Scope
- Collect legal/policy decisions for:
  - default retention period
  - deletion/anonymization SLA
  - export payload scope and redactions
  - immutable provenance handling policy
- Produce implementation-ready policy constants and decision record.
- Out of scope: building runtime workflows or UI.

## Inputs / Dependencies
- Story ST-013 acceptance criteria.
- Existing privacy policy and terms drafts.
- Legal/policy reviewer input (if available).

## Implementation Notes
- Capture unresolved items as explicit decision gaps with owner and due date.
- Define fallback defaults when approvals are pending (for non-production use only).
- Ensure resulting policy values map directly to config keys.

## Acceptance Criteria
1. A signed-off policy matrix exists with retention, export, and deletion rules.
2. Deletion SLA is quantified (for example, X calendar days) with owner approval.
3. Provenance immutability rule and exceptions are documented.
4. Open legal/policy gaps are tracked with owners and target resolution dates.

## Validation
- Policy review meeting completed and notes recorded.
- Cross-check matrix against ST-013 acceptance criteria.
- Product/engineering sign-off recorded.

## Deliverables
- Governance policy matrix document.
- Decision log/ADR for retention-export-deletion rules.
- Implementation constants map (policy value to config key).
