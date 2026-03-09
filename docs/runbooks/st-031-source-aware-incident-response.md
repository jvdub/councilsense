# ST-031 Source-Aware Incident Response Runbook

Task: TASK-ST-031-04

This is the primary runbook entry point for all ST-031 alert classes:

- `parser_drift_spike`
- `missing_minutes_surge`
- `summarize_failure_spike`
- `stale_pipeline_dlq_backlog`

Supporting references:

- `docs/runbooks/st-016-parser-drift-monitoring-runbook.md`
- `docs/runbooks/st-029-pipeline-dlq-contract.md`
- `docs/runbooks/st-010-health-and-confidence-policy.md`
- `docs/runbooks/st-021-quality-gates-rollout-and-rollback.md`

## Owner Routing And Alert-to-Action Matrix

| Alert class                  | Primary owner          | Secondary owner           | Escalate to      | Escalation SLA | Primary remediation action                                                                                                                                |
| ---------------------------- | ---------------------- | ------------------------- | ---------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `parser_drift_spike`         | `ops-ingestion-oncall` | `backend-oncall`          | `platform-owner` | `PT45M`        | Validate parser drift context, stop unplanned parser rollout, and route affected outputs to limited-confidence handling if source integrity is uncertain. |
| `missing_minutes_surge`      | `ops-ingestion-oncall` | `source-operations-owner` | `platform-owner` | `PT45M`        | Restore authoritative minutes coverage or explicitly hold the affected bundle in limited-confidence status until the source gap is resolved.              |
| `summarize_failure_spike`    | `ops-pipeline-oncall`  | `backend-oncall`          | `platform-owner` | `PT30M`        | Stabilize summarize execution, choose limited-confidence versus rollback using the decision tree below, and replay only after the root cause is fixed.    |
| `stale_pipeline_dlq_backlog` | `ops-pipeline-oncall`  | `backend-oncall`          | `platform-owner` | `PT30M`        | Drain the source-scoped DLQ backlog with auditable replay batches after the failure cause is corrected.                                                   |

Every handoff must preserve `alert_id`, `alert_class`, `severity`, `environment`, `city_id`, `source_id`, `run_id`, `meeting_id`, and `stage`.

## Common Triage Checklist

1. Acknowledge the page and record `acknowledged_by`, `acknowledged_at_utc`, and `acknowledgment_note`.
2. Open the dashboard panel named in the alert payload and confirm the affected `city_id`, `source_id`, `run_id`, and `meeting_id`.
3. Verify the incident scope is source-aware rather than global: one source, one city, or one stage before selecting remediation.
4. Decide whether the incident needs:
   - source repair without replay,
   - source-scoped replay after repair,
   - limited-confidence handling, or
   - rollout rollback.
5. If the page cannot be scoped because `city_id`, `source_id`, or `run_id` is missing, escalate immediately to the owning secondary owner because the payload is incomplete for safe remediation.

## Alert Procedures

### `parser_drift_spike`

1. Check whether `planned_parser_rollout_window` is active. If yes, confirm the parser name/version change matches the release plan and leave the alert in monitoring unless source output quality has degraded.
2. Review `delta_context_json`, `baseline_parser_name`, `baseline_parser_version`, `current_parser_name`, and `current_parser_version`.
3. Correlate the same `city_id` and `source_id` against source freshness, compose coverage, and summarize failures to determine whether parser drift is isolated or causing downstream regressions.
4. If the parser change is unplanned, assign `backend-oncall` to stop the rollout or revert the parser override for the affected source.
5. If published output quality is now uncertain, follow the confidence-policy decision tree and capture the limited-confidence decision metadata before closing the incident.
6. Escalate to `platform-owner` before `PT45M` or immediately if multiple cities/sources show the same unplanned parser change.

### `missing_minutes_surge`

1. Validate `coverage_ratio`, `missing_source_types`, and `available_source_types` against the source-aware dashboard for the affected bundle.
2. Check for `planned_source_maintenance_window` and confirm whether the missing minutes condition is expected maintenance or an unscheduled source gap.
3. If authoritative minutes are absent but agenda/packet artifacts still exist, keep the bundle in limited-confidence status and record the authority plus quality-gate reason codes using the confidence-policy procedure.
4. If the incident is caused by source registry/configuration error, correct the source configuration first and then queue a source-scoped replay for the affected stage and source only.
5. If the gap is upstream source silence, open or update the source owner incident and do not replay until new source artifacts are available.
6. Escalate to `platform-owner` before `PT45M` or sooner if the missing coverage spans multiple bundles for the same city.

### `summarize_failure_spike`

1. Confirm the failure rate from `failed_runs`, `total_runs`, `provider_used`, `fallback_reason`, `error_code`, and `error_type`.
2. Check whether the source inputs are intact. If summarize failures are provider-specific and source evidence is still good, use the confidence-policy decision tree to decide whether limited-confidence output is acceptable for the affected runs.
3. If the publish path is being blocked or downgraded incorrectly across multiple sources, invoke the rollback decision tree instead of hand-editing confidence outcomes.
4. After the root cause is fixed, replay only the affected source-scoped summarize or publish work and capture replay audit metadata.
5. Escalate to `platform-owner` before `PT30M` or immediately when the incident is provider-wide or spans more than one city.

### `stale_pipeline_dlq_backlog`

1. Query `pipeline_dlq_entries` for the affected `source_id`, `stage_name`, and `dlq_key`, and verify `terminal_reason`, `retry_policy_version`, `backlog_count`, and `oldest_age_seconds`.
2. Classify each entry as replayable, already safely materialized (`noop` guard), or dismissible without replay.
3. Correct the underlying source or stage failure before issuing replay. Do not use replay to probe an unresolved root cause.
4. Execute a source-scoped replay batch only after the pre-checks below pass, then verify the outcome in `pipeline_replay_audit_events`.
5. Escalate to `platform-owner` before `PT30M` or immediately when oldest age continues to rise after one replay batch or the same `dlq_key` fails twice after mitigation.

## Replay Procedure

Use this procedure for `summarize_failure_spike` and `stale_pipeline_dlq_backlog` incidents once root cause mitigation is complete.

### Replay Pre-Checks

1. Confirm the DLQ row or failed run is limited to the intended `city_id`, `source_id`, `run_id`, `meeting_id`, and `stage_name`.
2. Confirm the root cause is fixed and that replay will not reintroduce the same failure.
3. Confirm the target row is currently `open` or `triaged` and that no `active_dlq_replay_batch` is already draining the same scope.
4. If publish or summarize side effects already materialized, expect a guarded `noop` outcome and do not force a duplicate replay.

### Required Replay Audit Metadata

- `actor_user_id`
- `replay_reason`
- `idempotency_key`
- `incident_reference`
- `alert_class`
- `city_id`
- `source_id`
- `run_id`
- `meeting_id`
- `stage_name`
- expected terminal outcome

### Replay Steps

1. Record the replay metadata above before submitting the request.
2. Transition the DLQ row to `replay_ready` only when the scope and cause are understood.
3. Execute the replay request and follow `pipeline_replay_command` plus `pipeline_replay_execution` logs for the same correlation keys.
4. Verify a terminal event of `replayed`, `noop`, or `failed` in `pipeline_replay_audit_events`.
5. If the outcome is `noop`, record the `guard_reason_code` and close the incident only when the existing artifacts are still correct.
6. If the outcome is `failed`, stop replays, preserve the incident state, and escalate with the audit trail.

## Confidence-Policy Decision Tree

Use this procedure when `missing_minutes_surge`, `parser_drift_spike`, or `summarize_failure_spike` means output quality is uncertain but data can still be published in a bounded way.

1. If the issue is a source-quality or evidence-quality problem limited to one source or bundle, prefer limited-confidence handling over rollback.
2. If `confidence_score` is missing or below `MANUAL_REVIEW_CONFIDENCE_THRESHOLD`, route to `manual_review_needed`.
3. If `confidence_score` is between `MANUAL_REVIEW_CONFIDENCE_THRESHOLD` and `WARN_CONFIDENCE_THRESHOLD`, use `warn` and keep the reader-visible low-confidence indicator enabled.
4. If authoritative minutes are missing, parser drift is unplanned, or summarize output is incomplete, keep publication at `limited_confidence` until the source issue is resolved even when the raw score would otherwise pass.
5. If the problem is not source quality but enforcement misbehavior across many runs, do not override confidence locally. Move to the rollback decision tree.

### Required Confidence Audit Metadata

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

## Rollback Decision Tree

Use this procedure when enforcement controls, not source content, are causing unsafe broad publish behavior.

1. If multiple sources or cities are being incorrectly downgraded or blocked by document-aware enforcement, immediately revert `gate_mode` to `report_only`.
2. If report-only reversion restores expected publish behavior, stop there and keep any still-affected source-specific outputs in limited-confidence mode until source remediation is complete.
3. If behavior remains incorrect after `gate_mode=report_only`, disable document-aware feature flags in reverse order using ST-021.
4. Never perform schema rollback for ST-031 incidents.
5. If baseline behavior is not restored within 15 minutes of rollback start, escalate to the incident commander path defined in ST-030.

### Required Rollback Audit Metadata

- `actor_user_id`
- `incident_reference`
- `rollback_started_at_utc`
- `rollback_reason`
- `environment`
- `cohort`
- `previous_config_snapshot`
- `new_config_snapshot`
- `verification_run_id`
- `verification_result`

## Handoff And Closure Requirements

- Record the owning team, current mitigation, and next escalation time.
- Include one dashboard reference and one query or audit reference for the final incident note.
- Close the incident only after the terminal replay outcome, confidence decision, or rollback verification result is captured in the incident record.
