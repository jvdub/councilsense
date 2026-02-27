# CouncilSense Delivery Backlog (MVP + Phase 1.5)

This backlog is grounded in `REQUIREMENTS.md` (authoritative) with architecture alignment from `ARCHITECTURE.md`, `DB.md`, `BACKEND.md`, and `FRONTEND.md`.

## Phase Grouping

- **Phase 1 (MVP Pilot):** ST-001 through ST-013
- **Phase 1.5 (Hardening):** ST-014 through ST-016

## Ordered Backlog

| Order | Story ID | Title | Phase | Primary Requirement Coverage | Depends On |
|---|---|---|---|---|---|
| 1 | ST-001 | Managed Auth + Home City Onboarding | Phase 1 | MVP §4.1, FR-1, FR-2, FR-6 | None |
| 2 | ST-003 | City Registry + Source Configuration | Phase 1 | MVP §4.2, FR-3, FR-7 | ST-001 |
| 3 | ST-002 | Profile Preferences + Self-Service Controls | Phase 1 | MVP §4.1(4), MVP §4.4(4), FR-2, FR-5(4), FR-6 | ST-001 |
| 4 | ST-004 | Scheduled Ingestion + Processing Orchestration | Phase 1 | MVP §4.3, FR-3, FR-7(4), NFR-1 | ST-003 |
| 5 | ST-005 | Evidence-Grounded Summarization + Quality Gate | Phase 1 | MVP §4.3(2-4), FR-4, FR-7(3), NFR-7 | ST-004 |
| 6 | ST-006 | Meeting Reader API (City List + Detail) | Phase 1 | MVP §4.5(1-2), FR-6, NFR-2 | ST-002, ST-005 |
| 7 | ST-007 | Frontend Meetings List + Detail Experience | Phase 1 | MVP §4.5(1-3), FR-4, NFR-2 | ST-001, ST-006 |
| 8 | ST-008 | Notification Preferences + Push Subscriptions UI | Phase 1 | MVP §4.4(2-5), FR-2, FR-5(4-5), NFR-3 | ST-002, ST-007 |
| 9 | ST-009 | Idempotent Notification Fan-Out + Delivery | Phase 1 | MVP §4.4(1-4), FR-5, NFR-1, NFR-4 | ST-002, ST-005, ST-008 |
| 10 | ST-010 | Source Health + Manual Review Baseline | Phase 1 | FR-7, NFR-4, Phase 1 baseline (§9) | ST-003, ST-004, ST-005 |
| 11 | ST-011 | Observability Baseline for Pipeline + Notifications | Phase 1 | NFR-4, NFR-1, NFR-2 | ST-004, ST-009, ST-010 |
| 12 | ST-012 | Local-First + AWS Portable Runtime | Phase 1 | NFR-5, NFR-6, MVP §4.1-§4.5 parity | ST-001, ST-004, ST-007, ST-009 |
| 13 | ST-013 | Governance: Retention, Export, and Deletion Workflows | Phase 1 | NFR-3, NFR-7 | ST-002, ST-009, ST-011 |
| 14 | ST-014 | Phase 1.5: Notification DLQ + Replay Hardening | Phase 1.5 | FR-5 hardening, NFR-4, Phase 1.5 (§9) | ST-009, ST-011 |
| 15 | ST-015 | Phase 1.5: Quality Operations + ECR Audits | Phase 1.5 | FR-4, NFR-4, Success Metrics §8 (ECR) | ST-005, ST-010, ST-011 |
| 16 | ST-016 | Phase 1.5: Alert Thresholds + Parser Drift Monitoring | Phase 1.5 | FR-7(2), NFR-4 hardening, Phase 1.5 (§9) | ST-010, ST-011, ST-015 |

## Dependency Summary

- **Critical path (MVP):** ST-001 → ST-003 → ST-004 → ST-005 → ST-006 → ST-007 → ST-008 → ST-009 → ST-011.
- **Source operations branch:** ST-003 → ST-004 → ST-010 → ST-011.
- **Platform/governance branch:** ST-001/ST-004/ST-007/ST-009 → ST-012 and ST-002/ST-009/ST-011 → ST-013.
- **Hardening branch:** ST-009/ST-011 → ST-014, and ST-005/ST-010/ST-011 → ST-015 → ST-016.

## Notes on Scope Boundaries

- Backlog intentionally excludes items explicitly out of MVP scope: multi-city following per user, SMS, real-time alerts, advanced personalization, public API, and meeting Q&A/chat UI.
- Phase 1 includes baseline reliability/quality/source visibility controls required by MVP exit criteria.
- Phase 1.5 stories capture required hardening boundaries: DLQ/replay, audited ECR operations, parser drift monitoring, and alert thresholds.

## Review Outcome

- Story audit completed against `REQUIREMENTS.md`, `ARCHITECTURE.md`, `DB.md`, `BACKEND.md`, and `FRONTEND.md`.
- No story was removed or merged: each story maps to distinct MVP or Phase 1.5 requirements.
- Requirement traceability labels were normalized to canonical MVP/FR/NFR/Phase references.
