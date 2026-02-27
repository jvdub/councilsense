# Governance: Retention, Export, and Deletion Workflows

**Story ID:** ST-013  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** NFR-3, NFR-7, Pilot launch policy readiness (Requirements §7)

## User Story
As a privacy-conscious user, I want clear data retention and deletion/export workflows so my personal data is handled responsibly.

## Scope
- Define and implement retention policy defaults and enforcement hooks.
- Implement user data export workflow for profile/preferences/notification history.
- Implement user deletion/anonymization workflow within defined SLA.
- Ensure privacy policy and terms links are present in product surface.

## Acceptance Criteria
1. Data retention period is documented and configurable (default 24 months unless policy/legal override).
2. User export is available for profile/preferences/notification history.
3. User deletion request removes or anonymizes personal profile data within defined SLA.
4. Published provenance remains immutable append-only while respecting governance policy.
5. Privacy policy and terms links are visible before pilot launch.

## Implementation Tasks
- [ ] Implement governance tables/workflows for retention, export, and deletion requests.
- [ ] Build backend endpoints/jobs for export generation and deletion processing.
- [ ] Add UI entry points for data export and account deletion request.
- [ ] Add retention/archival policy job configuration and docs.
- [ ] Add compliance tests for anonymization and export completeness.

## Dependencies
- ST-002
- ST-009
- ST-011

## Definition of Done
- Governance workflows are operational and documented.
- User-facing policy links and request paths are in place.
- Compliance checks pass for export and deletion behavior.
