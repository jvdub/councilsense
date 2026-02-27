# AWS Baseline Wiring

**Task ID:** TASK-ST-012-04  
**Story:** ST-012  
**Bucket:** ops  
**Requirement Links:** NFR-6

## Objective
Wire baseline AWS runtime using managed services with the same application contracts.

## Scope
- In scope:
  - Baseline infrastructure definitions for web hosting, api/worker runtime, queue, storage, database, secrets.
  - Service configuration bindings to environment contract.
  - Minimal deployment pipeline entrypoint for staging.
- Out of scope:
  - Advanced scaling and hardening beyond baseline.

## Inputs / Dependencies
- TASK-ST-012-02
- TASK-ST-012-01

## Implementation Notes
- Keep infrastructure definitions version-controlled.
- Externalize secrets to cloud secret/config manager.
- Ensure observability endpoints are configured for ST-011 telemetry.

## Acceptance Criteria
1. Core services deploy to AWS without code forks.
2. Environment and secret bindings satisfy startup validation.
3. Baseline deployment supports core application flow in staging.

## Validation
- Run infrastructure plan/apply in staging context.
- Run post-deploy smoke checks for api, worker, queue, and storage connectivity.
- Verify telemetry emission in staging.

## Deliverables
- Infrastructure definition files.
- Deployment scripts/pipeline config.
- Staging deployment validation notes.
