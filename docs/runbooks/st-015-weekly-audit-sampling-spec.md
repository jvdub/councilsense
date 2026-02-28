# ST-015 Weekly Audit Sampling Spec and Schedule

## Purpose

Define the reproducible weekly sampling process used by quality operations to produce the ST-015 audited ECR report.

This artifact covers sampling and schedule only. ECR computation and reviewer queue execution are implemented in downstream tasks.

## Scope and Output

- Sampling frame for each audit week.
- Deterministic sample selection method and seed contract.
- Minimum representativeness rules across city/source.
- Weekly execution schedule and owner roles.
- Audit report schema contract consumed by downstream ECR job/report tasks.

## Audit Window Contract

- Time zone: UTC.
- Weekly window: Monday 00:00:00 UTC (inclusive) through next Monday 00:00:00 UTC (exclusive).
- `window_start_utc` is always ISO-8601 date (`YYYY-MM-DD`) for Monday.
- `window_end_utc = window_start_utc + 7 days`.

## Sampling Frame Eligibility

A publication is eligible for weekly sampling when all conditions hold:

1. `published_at` is in `[window_start_utc, window_end_utc)`.
2. `publication_status` is one of `processed`, `limited_confidence`.
3. Required identifiers are present and non-empty:
   - `publication_id`
   - `meeting_id`
   - `city_id`
   - `source_id`
4. `published_at` is timezone-aware and parseable as UTC timestamp.

Publications that fail any required condition are excluded from the sample and recorded in malformed exclusions.

## Sample Size and Selection Method

### Baseline sample size

- `sample_size_default = 60` publications per weekly window.
- If fewer than 60 eligible publications exist, sample all eligible publications.

### Deterministic seed

- Seed material: `seed = "st-015-weekly-ecr-audit|{window_start_utc}|{seed_salt}"`.
- Default `seed_salt = "v1"`.
- Candidate rank key is deterministic hash of `seed + publication_id`.

### Selection order

1. Build the eligible frame for the window.
2. Select city spread slots first.
3. Select source spread slots second (without duplicating selected records).
4. Fill remaining slots by deterministic global rank.

## Minimum Representativeness Rules

To reduce concentration in one city/source, each weekly sample enforces minimum spread targets when feasible:

- `min_city_slots = 3`
- `min_source_slots = 2`

Targets per week are:

- `target_city_slots = min(min_city_slots, distinct_city_count_in_frame, sample_size_actual_cap)`
- `target_source_slots = min(min_source_slots, distinct_source_count_in_frame, sample_size_actual_cap)`

If the frame is too small to satisfy both targets simultaneously, the report marks representativeness as `degraded` with explicit reason metadata.

## Malformed and Missing Data Handling

Excluded records are tracked with:

- `publication_id` (or fallback value `unknown`)
- `reason_code` from closed set:
  - `missing_publication_id`
  - `missing_meeting_id`
  - `missing_city_id`
  - `missing_source_id`
  - `missing_published_at`
  - `invalid_published_at_timezone`
  - `invalid_publication_status`

Malformed exclusions do not block audit run completion; they are surfaced in weekly report metadata and counted for operational triage.

## Weekly Schedule and Ownership

- Cadence: weekly, every Monday.
- Trigger time: `07:00 UTC`.
- SLA target: report artifact finalized by `09:00 UTC` the same day.
- Primary owner role: `ops-quality-oncall`.
- Backup owner role: `backend-oncall`.

Escalation and review:

1. If sampling/job execution fails, `ops-quality-oncall` initiates retry within 30 minutes.
2. If retry fails or representativeness is degraded for 2 consecutive weeks, escalate to product + engineering quality review in weekly ops standup.

## Report Schema Contract

Machine-readable contract artifact:

- `backend/tests/fixtures/st015_weekly_audit_report_schema_contract.json`

Scheduler configuration requirements artifact:

- `config/ops/st-015-weekly-ecr-audit-schedule.yaml`

## Reproducibility Validation Procedure

For any historical `window_start_utc`:

1. Run sample generation with fixed `seed_salt`.
2. Persist `selected_publication_ids` and sampling metadata.
3. Re-run with same inputs.
4. Confirm selected IDs are byte-for-byte identical and ordered identically.

Success criterion: deterministic rerun equality = `true`.
