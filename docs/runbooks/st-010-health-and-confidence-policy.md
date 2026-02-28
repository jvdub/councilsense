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

## Reader Implications

- Low-confidence indicator communicates reduced reliability for affected outputs.
- Missing confidence signal is treated as low-confidence by default to avoid silent false assurance.
