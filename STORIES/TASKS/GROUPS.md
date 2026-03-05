# Task Refinement Groups (Subagent Batches)

This file records the story grouping used to refine stories into task files.

## Group A — Identity + City + Pipeline Foundation

- ST-001 Managed Auth + Home City Onboarding
- ST-002 Profile Preferences + Self-Service Controls
- ST-003 City Registry + Source Configuration
- ST-004 Scheduled Ingestion + Processing Orchestration

## Group B — Quality + Reader + Frontend Reader UX + Push UI

- ST-005 Evidence-Grounded Summarization + Quality Gate
- ST-006 Meeting Reader API (City List + Detail)
- ST-007 Frontend Meetings List + Detail Experience
- ST-008 Notification Preferences + Push Subscriptions UI

## Group C — Notification Delivery + Source Ops + Observability + Runtime Portability

- ST-009 Idempotent Notification Fan-Out + Delivery
- ST-010 Source Health + Manual Review Baseline
- ST-011 Observability Baseline for Pipeline + Notifications
- ST-012 Local-First + AWS Portable Runtime

## Group D — Governance + Hardening

- ST-013 Governance: Retention, Export, and Deletion Workflows
- ST-014 Phase 1.5: Notification DLQ + Replay Hardening
- ST-015 Phase 1.5: Quality Operations + ECR Audits
- ST-016 Phase 1.5: Alert Thresholds + Parser Drift Monitoring

## Group E — Rubric Hardening + Additive Reader Contract

- ST-017 Phase 1.5: Rubric Freeze + Fixture Scorecard
- ST-018 Phase 1.5: Additive evidence_references Contract

## Group F — Topic Semantic + Specificity and Evidence Precision Hardening

- ST-019 Phase 1.5: Topic Semantic Hardening
- ST-020 Phase 1.5: Specificity + Evidence Locator Precision Hardening

## Group G — Quality Gates Enforcement, Rollout, and Rollback Controls

- ST-021 Phase 1.5: Quality Gates Enforcement, Rollout, and Rollback Controls

## Correlation Pattern

- Every task belongs to exactly one story folder: `STORIES/TASKS/ST-###/`.
- Story folder contains one `INDEX.md` plus task files.
- Task IDs use `TASK-ST-###-NN` and are only unique within the story.
- Cross-story dependencies are listed in the story `INDEX.md` and task `Inputs / Dependencies` sections.
