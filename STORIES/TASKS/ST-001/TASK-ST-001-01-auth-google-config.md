# Configure Google managed auth and local callbacks

**Task ID:** TASK-ST-001-01  
**Story:** ST-001  
**Bucket:** ops  
**Requirement Links:** FR-1, FR-6, NFR-5

## Objective
Enable Google-only managed auth with correct callback/logout URLs for local and dev environments.

## Scope
- Configure identity provider settings for Google sign-in.
- Configure app client callback/logout URLs for localhost and dev.
- Out of scope: frontend onboarding logic, backend authorization middleware.

## Inputs / Dependencies
- Story spec ST-001
- Existing auth infrastructure/config modules

## Implementation Notes
- Target auth IaC/config and environment variable wiring.
- Ensure Google is the only enabled social provider in MVP mode.

## Acceptance Criteria
1. Google sign-in configuration exists and validates in config/deploy checks.
2. Localhost callback/logout URLs are present and correct.
3. No other social providers are enabled in MVP config.

## Validation
- Run config/unit checks for auth config module.
- Execute local sign-in smoke flow and verify redirect URI success.

## Deliverables
- Updated auth configuration files and env templates.
- Brief note in docs/runbook for local callback values.
