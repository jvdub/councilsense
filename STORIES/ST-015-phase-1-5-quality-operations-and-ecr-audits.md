# Phase 1.5: Quality Operations + ECR Audits

**Story ID:** ST-015  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** FR-4, NFR-4, Success Metrics §8 (ECR), Phase 1.5 (§9)

## User Story
As a quality reviewer, I want recurring evidence-quality audits and confidence calibration so published summaries maintain trust at scale.

## Scope
- Implement weekly audited sample process for Evidence Coverage Rate (ECR).
- Implement reviewer workflow for low-confidence/low-evidence outputs.
- Add confidence calibration feedback loop into quality policy settings.

## Acceptance Criteria
1. Weekly quality audit report computes ECR from published samples.
2. Claims without adequate evidence are consistently labeled limited-confidence.
3. Reviewer workflow can record review outcome and recommended action.
4. Phase 1.5 operations target ECR >= 85% on audited weekly sample.
5. Audit outputs are visible to operations and product owners.

## Implementation Tasks
- [ ] Implement scheduled ECR audit job and report artifact.
- [ ] Implement reviewer queue/data model for low-confidence outputs.
- [ ] Add calibration configuration for confidence thresholds.
- [ ] Add dashboard/reporting view for ECR trend and reviewer outcomes.
- [ ] Add tests validating ECR computation and threshold handling.

## Dependencies
- ST-005
- ST-010
- ST-011

## Definition of Done
- Quality operations cadence is operational and documented.
- ECR trend and gate performance are measurable week over week.
- Reviewer feedback loop is actionable for model/policy tuning.
