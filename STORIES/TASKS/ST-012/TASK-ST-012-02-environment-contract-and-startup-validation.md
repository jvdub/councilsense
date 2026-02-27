# Environment Contract and Startup Validation

**Task ID:** TASK-ST-012-02  
**Story:** ST-012  
**Bucket:** backend  
**Requirement Links:** NFR-5, NFR-6

## Objective
Implement one environment variable contract and startup validation used by local and AWS deployments.

## Scope
- In scope:
  - Required and optional environment variable definitions.
  - Startup validation with clear failure messages.
  - Secret source abstraction compatible with local and cloud secret managers.
- Out of scope:
  - Full local runtime orchestration.
  - AWS provisioning details.

## Inputs / Dependencies
- TASK-ST-012-01

## Implementation Notes
- Fail fast on missing required settings.
- Support environment-specific defaults only where safe.
- Keep secrets out of code and logs.

## Acceptance Criteria
1. Application startup validates config contract in all services.
2. Missing required values produce actionable errors.
3. Same config keys are used locally and in AWS.

## Validation
- Run config validation tests with valid and invalid env sets.
- Run startup smoke for api and worker in local and cloud-like settings.

## Deliverables
- Config schema and validation module.
- Service startup integration updates.
- Validation test coverage.
