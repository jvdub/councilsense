# ST-010 Health and Confidence Policy Baseline

## Purpose

Define deterministic baseline policy rules for:

- source health status classification,
- confidence-based manual review routing,
- reader-facing low-confidence indication.

This policy is intentionally minimal for Phase 1 and maps directly to existing enum values in persistence contracts.

## Source Health Status Values

- `unknown`
- `healthy`
- `degraded`
- `failing`

## Source Health Transition Triggers

Inputs:

- `last_attempt_succeeded` (`true`, `false`, or missing `null` when no attempt has been recorded yet)
- `failure_streak` (non-negative integer)

Deterministic transition rules:

1. `last_attempt_succeeded = null` -> `unknown`
2. `last_attempt_succeeded = true` -> `healthy`
3. `last_attempt_succeeded = false` and `failure_streak >= 3` -> `failing`
4. `last_attempt_succeeded = false` and `failure_streak` in `[1,2]` -> `degraded`

Invalid input policy:

- `failure_streak < 0` is invalid and must fail fast.

## Confidence Threshold Policy

### Environment Configuration

- `MANUAL_REVIEW_CONFIDENCE_THRESHOLD` (default: `0.60`)
- `WARN_CONFIDENCE_THRESHOLD` (default: `0.80`)

Validation constraints:

- each threshold must be in inclusive range `[0.0, 1.0]`
- `WARN_CONFIDENCE_THRESHOLD >= MANUAL_REVIEW_CONFIDENCE_THRESHOLD`

### Deterministic Routing Rule

Input signal:

- `confidence_score` in `[0.0, 1.0]`, or missing

Outcomes:

1. Missing `confidence_score` -> `manual_review_needed`
2. `confidence_score < MANUAL_REVIEW_CONFIDENCE_THRESHOLD` -> `manual_review_needed`
3. `MANUAL_REVIEW_CONFIDENCE_THRESHOLD <= confidence_score < WARN_CONFIDENCE_THRESHOLD` -> `warn`
4. `confidence_score >= WARN_CONFIDENCE_THRESHOLD` -> `pass`

## Reader-Facing Low-Confidence Indicator Rule

The reader low-confidence indicator is set to `true` for outcomes:

- `manual_review_needed`
- `warn`

The indicator is set to `false` for outcome:

- `pass`

## Outcome Examples

- Pass: `confidence_score = 0.84` with defaults -> `pass`, reader indicator `false`
- Warn: `confidence_score = 0.72` with defaults -> `warn`, reader indicator `true`
- Manual review: `confidence_score = 0.43` with defaults -> `manual_review_needed`, reader indicator `true`
- Manual review (missing signal): `confidence_score = null` -> `manual_review_needed`, reader indicator `true`

## Operator Implications

- `failing` sources are top-priority intervention targets.
- `degraded` sources indicate active regression risk and require monitoring.
- `manual_review_needed` outcomes are triaged before broad consumption.

## Ownership And Escalation

- Primary owner for limited-confidence decisions: `ops-pipeline-oncall`
- Secondary owner for source-integrity decisions: `ops-ingestion-oncall`
- Escalate to: `platform-owner`
- Escalate when limited-confidence handling no longer isolates the issue to one source or bundle, or when enforcement behavior rather than source quality appears to be driving the downgrade.

## Limited-Confidence Incident Decision Tree

1. If the issue is missing or weak source evidence for one bundle or source, keep the outcome in `manual_review_needed` or `warn` and publish as `limited_confidence`.
2. If authoritative minutes are missing, treat the bundle as limited-confidence even when supplemental agenda or packet artifacts are present.
3. If parser drift or summarize degradation creates uncertain evidence, keep reader low-confidence indication enabled until the source-aware incident is remediated.
4. If multiple cities or sources are being downgraded because of enforcement controls rather than source content, stop confidence overrides and move to rollback handling.

## Required Confidence Audit Metadata

- `decision_actor`
- `decision_at_utc`
- `incident_reference`
- `city_id`
- `source_id`
- `run_id`
- `meeting_id`
- `confidence_score`
- `confidence_outcome`
- `publication_status`
- `authority_reason_codes`
- `quality_gate_reason_codes`
- `decision_reason`

## Reader Implications

- Low-confidence indicator communicates reduced reliability for affected outputs.
- Missing confidence signal is treated as low-confidence by default to avoid silent false assurance.
