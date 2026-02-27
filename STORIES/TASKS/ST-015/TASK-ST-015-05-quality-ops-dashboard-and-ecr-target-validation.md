# Quality Operations Dashboard and ECR Target Validation

**Task ID:** TASK-ST-015-05  
**Story:** ST-015  
**Bucket:** ops  
**Requirement Links:** NFR-4, Success Metrics §8 (ECR), ST-015 Acceptance Criteria #4 and #5

## Objective
Provide operations visibility and release evidence for weekly quality performance, including ECR >= 85% target tracking.

## Scope
- Add dashboard views for ECR trend, low-confidence rate, and reviewer outcomes.
- Add weekly quality report summary with target status.
- Define escalation path when ECR falls below target.
- Out of scope: changing core audit math or queue business rules.

## Inputs / Dependencies
- TASK-ST-015-02 audit artifacts.
- TASK-ST-015-03 reviewer outcomes.
- TASK-ST-015-04 threshold policy metadata.

## Implementation Notes
- Minimum measurable outputs:
  - weekly ECR
  - ECR target attainment (>= 85%)
  - low-confidence labeling rate
  - reviewer queue closure rate
- Include clear ownership for response to below-target weeks.

## Acceptance Criteria
1. Dashboard shows weekly ECR trend and target attainment status.
2. Reviewer outcomes and queue backlog are visible to operations/product owners.
3. Weekly report flags target misses with escalation owner and timestamp.
4. Historical reports are retained for week-over-week comparison.

## Validation
- Dashboard query verification against known audit fixtures.
- Weekly report generation smoke test.
- Simulated below-target week to validate escalation signal.

## Deliverables
- Dashboard panels and report templates.
- Escalation/runbook entry for ECR target misses.
- Weekly quality evidence package for hardening reviews.
