# ST-016 Parser Drift Monitoring Runbook

## Scope

Use this runbook when ST-016 parser drift telemetry reports a parser name/version change for active city sources.

- Event schema: `st016.parser_drift_event.v1`
- Event store: `parser_drift_events`
- Dashboard linkage: `docs/runbooks/st-016-synthetic-alert-validation-dashboard.json` panel `st016-parser-drift-events-weekly`

## Ownership and Escalation

- Primary owner: `ops-ingestion-oncall`
- Secondary owner: `backend-oncall`
- Escalate to: `platform-owner`
- Escalation SLA: `PT45M`

## Required Triage Context

Each parser drift event must include:

- `city_id`
- `source_id`
- `baseline_run_id`
- `run_id`
- `baseline_parser_name`
- `baseline_parser_version`
- `current_parser_name`
- `current_parser_version`
- `delta_context_json`

## Triage Steps

1. Validate whether drift is expected from the current release train.
2. Inspect `delta_context_json` changed fields and confirm parser contract compatibility.
3. Correlate with source freshness and pipeline latency for the same `city_id` and `source_id`.
4. If parser drift is unplanned, open remediation incident and assign parser owner.
