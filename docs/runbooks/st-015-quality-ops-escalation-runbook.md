# ST-015 Quality Ops ECR Escalation Runbook

Use this runbook when weekly ST-015 quality reporting shows ECR below the release target (>= 85%).

## Owners

- Primary owner role: `ops-quality-oncall`
- Secondary stakeholders: product owner, calibration owner

## Trigger

Escalation is required when the weekly report has:

- `target_status = below_target`
- `ecr < 0.85`
- non-null `escalation_triggered_at_utc`

## Response Steps

1. Open the latest dashboard view from `docs/runbooks/st-015-quality-ops-dashboard.json`.
2. Confirm ECR decline scope using `quality_ops_weekly_reports` trend rows.
3. Inspect reviewer outcome mix (`requires_reprocess`, `confirmed_issue`, `policy_adjustment_recommended`).
4. Validate active calibration policy version and compare with the previous week.
5. Create an incident note with the week start, ECR delta, and expected remediation owner.
6. Track closure criteria: ECR recovered to >= 0.85 in a subsequent weekly report.

## Evidence Package

For every below-target week, record:

- weekly summary payload from `quality_ops_weekly_reports.summary_json`
- reviewer backlog counts and closure rate
- reviewer outcome distribution for the same week
- calibration policy version and any follow-up policy update reference

## Exit Criteria

Escalation closes when:

- one full weekly cycle returns to `target_status = met`
- evidence package is attached to hardening review notes
- product owner acknowledges the recovery in weekly quality review
