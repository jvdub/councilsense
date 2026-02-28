# ST-011 Smoke + Triage Rehearsal Evidence

Date: 2026-02-28  
Story: ST-011  
Task: TASK-ST-011-05 — Smoke Validation and Triage Runbook

## Rehearsal Scope

- Environment: `aws` (non-local target)
- Dashboard: `st-011-baseline-ops`
- Drill scenarios:
  - Pipeline stage failure triage
  - Notification delivery failure triage
  - Stale/failing source triage

## Drill Outcome Summary

- Pipeline failure scenario: PASS (failure isolated to stage and correlated by `run_id`).
- Notification failure scenario: PASS (retry vs terminal outcomes separated and triaged).
- Stale source scenario: PASS (affected `city_id` + `source_id` identified from snapshot panel).

## End-to-End Execution Notes

1. Smoke checklist from `docs/runbooks/st-011-smoke-validation-checklist.md` executed end-to-end.
2. Each failure mode executed using mapped dashboard panel and log query from `docs/runbooks/st-011-triage-runbook.md`.
3. Evidence captured: dashboard snapshot, pipeline query snippet, notification query snippet.

## Follow-Ups

- No blocking gaps for MVP baseline observability readiness.
- Alert threshold tuning and escalation hardening deferred to Phase 1.5 work.
