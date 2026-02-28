# ST-011 Smoke Validation Checklist (Non-Local)

Use this checklist in a non-local environment (for example, `aws`) to verify baseline observability readiness for ST-011.

## Preconditions

- Dashboard config from `docs/runbooks/st-011-baseline-dashboards.json` is deployed.
- Environment filter is set to a non-local target (`aws`).
- At least one pipeline run and one notification delivery attempt were executed in the last 6 hours.

## Smoke Checks

- [ ] `pipeline-stage-outcomes` panel shows data points for at least one pipeline stage/outcome pair.
- [ ] `pipeline-stage-duration-p95` panel shows at least one p95 duration series.
- [ ] `notification-enqueue-outcomes` panel shows at least one enqueue outcome.
- [ ] `notification-delivery-outcomes` panel shows at least one delivery outcome.
- [ ] `notification-delivery-duration-p95` panel shows at least one p95 delivery duration value.
- [ ] `source-freshness-and-failure-snapshot` panel loads rows (including empty-state confirmation if no sources are stale/failing).
- [ ] Structured logs for `pipeline_stage_finished` OR `pipeline_stage_error` exist for the same window.
- [ ] Structured logs for `notification_delivery_attempt` exist for the same window.

## Minimum Evidence Package

Capture and retain all of the following:

1. Timestamped dashboard screenshot or export with environment filter visible.
2. One log query result snippet for pipeline (`pipeline_stage_finished` or `pipeline_stage_error`).
3. One log query result snippet for notifications (`notification_delivery_attempt`).
4. Rehearsal drill notes showing triage start time, diagnosis, mitigation, and closure time.

## Evidence Retention Location

- Canonical rehearsal notes file: `docs/runbooks/st-011-smoke-rehearsal-evidence.md`.
- Supporting screenshots and query snippets: committed in the same pull request as this checklist or linked from that notes file.
