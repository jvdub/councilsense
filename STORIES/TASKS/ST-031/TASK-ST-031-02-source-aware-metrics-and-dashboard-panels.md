# Source-Aware Metrics and Dashboard Panels

**Task ID:** TASK-ST-031-02  
**Story:** ST-031  
**Bucket:** ops  
**Requirement Links:** ST-031 Acceptance Criteria #2, AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §6 Testing and validation plan

## Objective

Instrument and publish source-aware metrics with dashboards for pipeline outcomes, quality indicators, and DLQ health.

## Scope

- Define and emit metrics for ingest/extract/compose outcomes by source type.
- Add quality-indicator metrics for coverage ratio and citation precision ratio.
- Add DLQ backlog and backlog-age metrics with source/city dimensions.
- Out of scope: alert routing policy and runbook ownership documentation.

## Inputs / Dependencies

- TASK-ST-031-01 structured log/correlation dimensions.
- Existing metrics export and dashboard stack.
- AGENDA_PLAN quality and DLQ observability indicators.

## Implementation Notes

- Keep metric names, labels, and units stable and documented.
- Use dimension cardinality controls to avoid high-cardinality regressions.
- Provide dashboard panels aligned to on-call triage order.

## Acceptance Criteria

1. Dashboards expose source-type outcomes, coverage ratio, citation precision ratio, and DLQ backlog/age.
2. Metrics include dimensions required for city/source troubleshooting.
3. Dashboard panels support per-stage and per-source diagnosis without ad hoc queries.
4. Metric definitions are documented for operator interpretation.

## Validation

- Verify metric emission across representative success/failure pipeline runs.
- Confirm dashboard panels populate with expected labels and time-series behavior.
- Check metric cardinality and scrape stability under load.

## Deliverables

- Source-aware metric contract and instrumentation checklist.
- Dashboard panel definitions and ownership mapping.
- Validation report for metric and dashboard correctness.
