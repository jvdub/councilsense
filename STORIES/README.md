# CouncilSense Delivery Backlog (MVP + Phase 1.5)

This backlog is grounded in `REQUIREMENTS.md` (authoritative) with architecture alignment from `ARCHITECTURE.md`, `DB.md`, `BACKEND.md`, and `FRONTEND.md`.

## Phase Grouping

- **Phase 1 (MVP Pilot):** ST-001 through ST-013
- **Phase 1.5 (Hardening):** ST-014 through ST-021
- **Phase 2 (Agenda Program Foundations):** ST-022 through ST-024
- **Phase 3 (Agenda Program Reader Rollout):** ST-025 through ST-031
- **Phase 4 (Resident Relevance + Explainability):** ST-032 through ST-035

## Ordered Backlog

| Order | Story ID | Title                                                 | Phase     | Primary Requirement Coverage                  | Depends On                     |
| ----- | -------- | ----------------------------------------------------- | --------- | --------------------------------------------- | ------------------------------ |
| 1     | ST-001   | Managed Auth + Home City Onboarding                   | Phase 1   | MVP §4.1, FR-1, FR-2, FR-6                    | None                           |
| 2     | ST-003   | City Registry + Source Configuration                  | Phase 1   | MVP §4.2, FR-3, FR-7                          | ST-001                         |
| 3     | ST-002   | Profile Preferences + Self-Service Controls           | Phase 1   | MVP §4.1(4), MVP §4.4(4), FR-2, FR-5(4), FR-6 | ST-001                         |
| 4     | ST-004   | Scheduled Ingestion + Processing Orchestration        | Phase 1   | MVP §4.3, FR-3, FR-7(4), NFR-1                | ST-003                         |
| 5     | ST-005   | Evidence-Grounded Summarization + Quality Gate        | Phase 1   | MVP §4.3(2-4), FR-4, FR-7(3), NFR-7           | ST-004                         |
| 6     | ST-006   | Meeting Reader API (City List + Detail)               | Phase 1   | MVP §4.5(1-2), FR-6, NFR-2                    | ST-002, ST-005                 |
| 7     | ST-007   | Frontend Meetings List + Detail Experience            | Phase 1   | MVP §4.5(1-3), FR-4, NFR-2                    | ST-001, ST-006                 |
| 8     | ST-008   | Notification Preferences + Push Subscriptions UI      | Phase 1   | MVP §4.4(2-5), FR-2, FR-5(4-5), NFR-3         | ST-002, ST-007                 |
| 9     | ST-009   | Idempotent Notification Fan-Out + Delivery            | Phase 1   | MVP §4.4(1-4), FR-5, NFR-1, NFR-4             | ST-002, ST-005, ST-008         |
| 10    | ST-010   | Source Health + Manual Review Baseline                | Phase 1   | FR-7, NFR-4, Phase 1 baseline (§9)            | ST-003, ST-004, ST-005         |
| 11    | ST-011   | Observability Baseline for Pipeline + Notifications   | Phase 1   | NFR-4, NFR-1, NFR-2                           | ST-004, ST-009, ST-010         |
| 12    | ST-012   | Local-First + AWS Portable Runtime                    | Phase 1   | NFR-5, NFR-6, MVP §4.1-§4.5 parity            | ST-001, ST-004, ST-007, ST-009 |
| 13    | ST-013   | Governance: Retention, Export, and Deletion Workflows | Phase 1   | NFR-3, NFR-7                                  | ST-002, ST-009, ST-011         |
| 14    | ST-014   | Phase 1.5: Notification DLQ + Replay Hardening        | Phase 1.5 | FR-5 hardening, NFR-4, Phase 1.5 (§9)         | ST-009, ST-011                 |
| 15    | ST-015   | Phase 1.5: Quality Operations + ECR Audits            | Phase 1.5 | FR-4, NFR-4, Success Metrics §8 (ECR)         | ST-005, ST-010, ST-011         |
| 16    | ST-016   | Phase 1.5: Alert Thresholds + Parser Drift Monitoring | Phase 1.5 | FR-7(2), NFR-4 hardening, Phase 1.5 (§9)      | ST-010, ST-011, ST-015         |
| 17    | ST-017   | Phase 1.5: Rubric Freeze + Fixture Scorecard          | Phase 1.5 | GAP_PLAN §Parity Targets, §Fixture + Scorecard | ST-005, ST-011, ST-012         |
| 18    | ST-018   | Phase 1.5: Additive evidence_references Contract      | Phase 1.5 | GAP_PLAN §Phase 1, §Gate A, FR-6              | ST-006, ST-017                 |
| 19    | ST-019   | Phase 1.5: Topic Semantic Hardening                   | Phase 1.5 | GAP_PLAN §Phase 2, §Gate B, FR-4              | ST-005, ST-017, ST-018         |
| 20    | ST-020   | Phase 1.5: Specificity + Evidence Locator Precision Hardening | Phase 1.5 | GAP_PLAN §Phase 3, §Gate B, FR-4      | ST-017, ST-018, ST-019         |
| 21    | ST-021   | Phase 1.5: Quality Gates Enforcement, Rollout, and Rollback Controls | Phase 1.5 | GAP_PLAN §Phase 4, §Gate Matrix, §Rollback | ST-014, ST-016, ST-017, ST-018, ST-019, ST-020 |
| 22    | ST-022   | Agenda Plan: v1 Contract, Schema, and Rollout Freeze | Phase 2   | AGENDA_PLAN §4, §5, §6                        | ST-006, ST-017, ST-021         |
| 23    | ST-023   | Agenda Plan: Meeting Bundle Planner and Source-Scoped Ingestion | Phase 2 | AGENDA_PLAN §3, §5, §6                     | ST-004, ST-022                 |
| 24    | ST-024   | Agenda Plan: Canonical Documents, Artifacts, and Spans Persistence | Phase 2 | AGENDA_PLAN §4, §5, NFR-4                | ST-022, ST-023                 |
| 25    | ST-025   | Agenda Plan: Authority-Aware Multi-Document Compose and Limited-Confidence Policy | Phase 3 | AGENDA_PLAN §3, §5, §8              | ST-005, ST-023, ST-024         |
| 26    | ST-026   | Agenda Plan: Evidence v2 Linkage, Precision Ladder, and Deterministic Ordering | Phase 3 | AGENDA_PLAN §3, §4, §5                 | ST-018, ST-024, ST-025         |
| 27    | ST-027   | Agenda Plan: Reader API Additive Planned/Outcomes and Mismatch Fields | Phase 3 | AGENDA_PLAN §3, §4, §5, FR-6            | ST-006, ST-022, ST-026         |
| 28    | ST-028   | Agenda Plan: Frontend Planned/Outcomes and Mismatch Rendering | Phase 3 | AGENDA_PLAN §3, §5, FR-4                 | ST-007, ST-027                 |
| 29    | ST-029   | Agenda Plan: Pipeline Retry Classification, DLQ, and Replay Audit | Phase 3 | AGENDA_PLAN §6, §8, NFR-4               | ST-014, ST-023, ST-025         |
| 30    | ST-030   | Agenda Plan: Document-Aware Quality Gates and Authority Alignment Enforcement | Phase 3 | AGENDA_PLAN §5, §6, §8             | ST-021, ST-025, ST-026, ST-029 |
| 31    | ST-031   | Agenda Plan: Multi-Document Observability, Alerts, and Runbook Completion | Phase 3 | AGENDA_PLAN §6, NFR-4                  | ST-011, ST-029, ST-030         |
| 32    | ST-032   | Resident Relevance: Structured Subject, Location, and Impact Extraction | Phase 4 | FR-4, REQUIREMENTS §12.2, §13.1, §13.2, §13.5, §14(10-11) | ST-020, ST-025, ST-026 |
| 33    | ST-033   | Resident Relevance: Reader API Additive Subject, Location, and Impact Fields | Phase 4 | FR-4, FR-6, REQUIREMENTS §12.2, §12.3, §13.1, §13.5, §14(3,10) | ST-027, ST-032 |
| 34    | ST-034   | Resident Relevance: Meeting Detail Impact Cards and Scan View | Phase 4 | FR-4, REQUIREMENTS §12.3, §13.1, §13.2, §13.5, §14(3,10) | ST-007, ST-028, ST-033 |
| 35    | ST-035   | Resident Relevance: Evidence-Backed Follow-Up Prompts for Meeting Detail | Phase 4 | FR-4, REQUIREMENTS §12.2, §12.3, §12.4, §13.1, §13.2, §13.5 | ST-032, ST-033, ST-034 |

## Dependency Summary

- **Critical path (MVP):** ST-001 → ST-003 → ST-004 → ST-005 → ST-006 → ST-007 → ST-008 → ST-009 → ST-011.
- **Source operations branch:** ST-003 → ST-004 → ST-010 → ST-011.
- **Platform/governance branch:** ST-001/ST-004/ST-007/ST-009 → ST-012 and ST-002/ST-009/ST-011 → ST-013.
- **Hardening branch:** ST-009/ST-011 → ST-014, and ST-005/ST-010/ST-011 → ST-015 → ST-016.
- **Gap-plan quality hardening chain:** ST-017 → ST-018 → ST-019 → ST-020 → ST-021.
- **Gate enablement dependency:** ST-014/ST-016 and ST-017 through ST-020 converge at ST-021 for shadow-to-enforced rollout and rollback control.
- **Agenda foundation chain:** ST-022 → ST-023 → ST-024 → ST-025 → ST-026 → ST-027 → ST-028.
- **Agenda operational hardening chain:** ST-023/ST-025 → ST-029 → ST-030 → ST-031.
- **Resident relevance chain:** ST-032 → ST-033 → ST-034 → ST-035.

## Notes on Scope Boundaries

- Backlog intentionally excludes items explicitly out of MVP scope: multi-city following per user, SMS, real-time alerts, advanced personalization, public API, and meeting Q&A/chat UI.
- Phase 1 includes baseline reliability/quality/source visibility controls required by MVP exit criteria.
- Phase 1.5 stories capture required hardening boundaries: DLQ/replay, audited ECR operations, parser drift monitoring, rubric freeze, additive evidence safety, specificity hardening, and controlled rollout/rollback.
- Phase 2 and Phase 3 extend the platform into document-aware agenda/packet/minutes ingestion, additive reader APIs, frontend rendering, and operational hardening.
- Phase 4 focuses on resident relevance and explainability so readers can see what changed, where it applies, and why it may matter without needing a full chat workflow.

## Review Outcome

- Story audit completed against `REQUIREMENTS.md`, `ARCHITECTURE.md`, `DB.md`, `BACKEND.md`, and `FRONTEND.md`.
- No story was removed or merged: each story maps to distinct MVP, agenda-program, or resident-relevance requirements.
- Requirement traceability labels were normalized to canonical MVP/FR/NFR/Phase references.

## Task Decomposition Pattern (for AI agents)

- Task organization conventions are defined in [STORIES/TASKS/README.md](TASKS/README.md).
- Task instances are created for every story under `STORIES/TASKS/ST-###/`.
- Each task maps to exactly one story using `TASK-ST-###-NN` IDs.
