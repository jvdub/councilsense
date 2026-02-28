# ST-013 Governance Policy + SLA Baseline

**Date:** 2026-02-28  
**Story:** ST-013  
**Task:** TASK-ST-013-01  
**Requirement Links:** NFR-3, NFR-7, Requirements §7, ST-013 AC(1-5)

## Decisions (Locked for MVP Baseline)

- Default retention period is **24 months** for raw artifacts and generated meeting outputs unless legal policy overrides are approved.
- User deletion/anonymization requests have a fulfillment SLA of **30 calendar days** from accepted request timestamp.
- Export scope is limited to user profile, preferences, and notification history; excluded/sensitive internal metadata is redacted.
- Published summary provenance is immutable append-only; corrections are additive and never mutate historical published provenance records.

## Governance Policy Matrix (Implementation Baseline)

| Policy area | Locked baseline | Enforcement expectation | Owner approval |
| --- | --- | --- | --- |
| Retention default | 24 months (`730` days) for raw artifacts + generated outputs | Configurable value, retention/archival jobs must read from policy key | Product + Engineering approved 2026-02-28 |
| Deletion/anonymization SLA | Complete within 30 calendar days from accepted request | Workflow stores request timestamp and due-at timestamp; breach is observable | Product + Engineering approved 2026-02-28 |
| Export payload scope | Include profile, preferences, notification history; include generated export metadata | Export workflow omits secrets/internal operational metadata | Product + Engineering approved 2026-02-28 |
| Export redactions | Redact push endpoint keys/tokens, internal auth/session data, internal failure traces | Export contract enforces allow-list fields only | Product + Engineering approved 2026-02-28 |
| Provenance immutability | Published provenance records are append-only immutable | No in-place update of published provenance rows/documents | Product + Engineering approved 2026-02-28 |

## Provenance Immutability Rule + Exceptions

### Rule

- Once a summary/provenance record is published, its provenance payload is immutable.
- Any correction is represented as a new appended record with linkage to prior record IDs.

### Allowed exceptions

- **Compliance takedown event:** record may be tombstoned for legal compliance, but original identifier and takedown reason metadata remain in immutable audit history.
- **Storage corruption recovery:** restored record must preserve original provenance identifier and include recovery audit metadata; no silent in-place mutation.

## Export Scope and Redaction Baseline

### Included in export

- User profile: user identifier, email, home city, created/updated timestamps.
- User preferences: notification enabled state, pause windows, related preference timestamps.
- Notification history: sent/attempted notification event history tied to the user.

### Excluded/redacted

- Push subscription cryptographic key material (`p256dh`, `auth`) and raw push endpoint URLs.
- Internal auth/session artifacts, secrets, and token material.
- Internal operator-only failure traces and transport diagnostics not needed for user portability.

## ADR-Style Decision Log

| Decision ID | Topic | Decision | Status | Owner | Date |
| --- | --- | --- | --- | --- | --- |
| GOV-013-001 | Retention default | Set baseline retention to 24 months configurable via environment key | Accepted | Product + Engineering | 2026-02-28 |
| GOV-013-002 | Deletion SLA | Set deletion/anonymization SLA to 30 calendar days | Accepted | Product + Engineering | 2026-02-28 |
| GOV-013-003 | Export scope | Limit export to profile/preferences/notification history with allow-list schema | Accepted | Product + Engineering | 2026-02-28 |
| GOV-013-004 | Provenance immutability | Enforce append-only provenance; use additive correction records | Accepted | Product + Engineering | 2026-02-28 |

## Implementation Constants Map (Policy -> Config Key)

| Policy constant | Config key | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| Retention period (days) | `GOVERNANCE_RETENTION_DAYS` | integer | `730` | Applies to raw artifacts + generated outputs |
| Deletion SLA (days) | `GOVERNANCE_DELETION_SLA_DAYS` | integer | `30` | Calendar-day SLA from accepted request |
| Export scope profile | `GOVERNANCE_EXPORT_INCLUDE_PROFILE` | boolean | `true` | Keep enabled for MVP |
| Export scope preferences | `GOVERNANCE_EXPORT_INCLUDE_PREFERENCES` | boolean | `true` | Keep enabled for MVP |
| Export scope notification history | `GOVERNANCE_EXPORT_INCLUDE_NOTIFICATION_HISTORY` | boolean | `true` | Keep enabled for MVP |
| Export redact push endpoint URL | `GOVERNANCE_EXPORT_REDACT_PUSH_ENDPOINT` | boolean | `true` | Prevents endpoint disclosure |
| Export redact push keys | `GOVERNANCE_EXPORT_REDACT_PUSH_KEYS` | boolean | `true` | Redacts `p256dh` and `auth` values |
| Provenance append-only guardrail | `GOVERNANCE_PROVENANCE_APPEND_ONLY` | boolean | `true` | Must stay true in production |

## Pending Legal/Policy Gaps (Tracked)

| Gap | Current fallback (non-production only) | Owner | Target resolution date | Status |
| --- | --- | --- | --- | --- |
| Jurisdiction-specific retention override list | Use `730`-day baseline globally | Legal/Policy | 2026-03-08 | Open |
| Compliance takedown legal rubric | Allow tombstone with immutable audit metadata only | Legal/Policy | 2026-03-08 | Open |
| Export redaction list legal confirmation | Use documented redaction allow-list baseline | Legal/Policy | 2026-03-10 | Open |

## Validation Evidence

- Cross-checked against ST-013 acceptance criteria AC(1-5): retention default/configurable, export scope, deletion SLA, provenance immutability, policy-readiness documentation.
- Product/engineering baseline approval recorded for implementation start; legal/policy gaps explicitly tracked with owners and target dates.
- Artifact is implementation-ready for TASK-ST-013-02 and downstream workflow tasks.
