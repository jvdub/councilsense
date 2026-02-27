# Synthetic Alert Validation, Dashboard Visibility, and Runbook Linkage

**Task ID:** TASK-ST-016-05  
**Story:** ST-016  
**Bucket:** tests  
**Requirement Links:** NFR-4, ST-016 Acceptance Criteria #5

## Objective
Validate end-to-end alerting and drift/freshness observability with synthetic tests and dashboard/runbook integration.

## Scope
- Build synthetic scenarios to trigger each alert class and drift/freshness signals.
- Add dashboard panels for alert volume, drift events, and freshness breaches.
- Link each alert class to triage runbook and ownership metadata.
- Out of scope: introducing new alert classes beyond ST-016 scope.

## Inputs / Dependencies
- TASK-ST-016-02 alert rules.
- TASK-ST-016-03 drift event model.
- TASK-ST-016-04 freshness alerts.

## Implementation Notes
- Minimum measurable outputs:
  - alert trigger success rate in synthetic tests
  - median detection latency from injected event to alert
  - parser drift events per week
  - freshness breach count per week
- Treat missing runbook link as validation failure.

## Acceptance Criteria
1. Synthetic tests trigger all configured alert classes successfully.
2. Dashboard displays alert, drift, and freshness signals with owner context.
3. Every alert class has linked runbook and explicit owner mapping.
4. Detection latency and trigger success metrics are reported.

## Validation
- Run synthetic alert suite in staging.
- Verify dashboard panels populate from synthetic events.
- Perform runbook-link completeness check across alert classes.

## Deliverables
- Synthetic alert test suite and fixtures.
- Dashboard updates for hardening visibility.
- Validation report with measurable hardening outputs.
