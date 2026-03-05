# API Contract Release Notes and Verification Runbook

**Task ID:** TASK-ST-018-05  
**Story:** ST-018  
**Bucket:** docs  
**Requirement Links:** FR-6, NFR-2, ST-018 Acceptance Criteria #4 and #5

## Objective
Publish operator/developer-facing release notes and runbook steps for verifying `evidence_references` contract behavior post-change.

## Scope
- Document additive contract summary and consumer impact guidance.
- Add verification runbook steps for evidence-present and evidence-sparse checks.
- Provide rollback/mitigation notes for unexpected contract regressions.
- Out of scope: introducing operational alerting changes unrelated to ST-018.

## Inputs / Dependencies
- TASK-ST-018-04 Gate A regression results.
- Existing reader API runbooks and release documentation conventions.

## Implementation Notes
- Keep runbook checks command-driven and reproducible by an agent.
- Include expected output signatures for quick pass/fail triage.
- Explicitly state that field is additive and backward compatible.

## Acceptance Criteria
1. Release notes describe additive field behavior and zero-breaking-change expectations.
2. Runbook includes concrete verification steps for both evidence scenarios.
3. Rollback/mitigation path is documented for contract regressions.
4. Story handoff packet includes links to contract tests and Gate A evidence.

## Validation
- Dry-run runbook verification steps against latest local environment.
- Confirm release notes align with contract decision and regression evidence.

## Deliverables
- API release notes update for `evidence_references`.
- Verification runbook section with command steps and expected outcomes.
- Handoff checklist linking tests, evidence artifacts, and mitigation guidance.
