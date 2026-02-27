# Local-First + AWS Portable Runtime

**Story ID:** ST-012  
**Phase:** Phase 1 (MVP)  
**Requirement Links:** NFR-5, NFR-6, MVP §4.1-§4.5 (parity enabler)

## User Story
As a developer/operator, I want the same product contracts to run locally and on AWS so delivery is fast and reliable without forked code paths.

## Scope
- Ensure full user journey runs locally with configuration-driven differences.
- Define cloud deployment baseline (Amplify + container backend + queue + storage).
- Standardize config/secrets handling across local and cloud.

## Acceptance Criteria
1. Local environment supports signup, city onboarding, processing, and reader flows.
2. Core services deploy to AWS with no separate codebase.
3. Environment differences are config-driven, not branch-driven.
4. Cloud deployment uses managed services to minimize operational overhead.
5. Secrets are externalized in cloud secret/config managers.

## Implementation Tasks
- [ ] Create local compose/runtime scripts for web, API, worker, DB, storage, queue adapter.
- [ ] Define environment variable contract and validation in startup.
- [ ] Implement cloud infrastructure baseline wiring (Amplify/App Runner/SQS/S3/RDS).
- [ ] Add deployment docs and smoke checks for local and cloud.
- [ ] Add parity checklist to CI/release process.

## Dependencies
- ST-001
- ST-004
- ST-007
- ST-009

## Definition of Done
- Team can run and demo full MVP journey locally.
- Cloud deployment executes same contracts with configuration changes only.
- Deployment docs and smoke checks are complete and current.
