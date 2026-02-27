# Self-Service Governance UI and Compliance Validation

**Task ID:** TASK-ST-013-05  
**Story:** ST-013  
**Bucket:** frontend  
**Requirement Links:** NFR-3, Requirements §7, ST-013 Acceptance Criteria #5

## Objective
Add user-facing entry points for export/deletion requests and ensure privacy policy and terms links are visible in product flows.

## Scope
- Add UI controls to submit export and deletion requests.
- Surface request status where applicable.
- Add visible privacy policy and terms links in required surfaces.
- Out of scope: backend request processing implementation.

## Inputs / Dependencies
- TASK-ST-013-03 export API.
- TASK-ST-013-04 deletion API.
- Approved policy/terms URLs from task 01.

## Implementation Notes
- Keep UX minimal and explicit: request action, confirmation, and status.
- Ensure links are available pre-pilot in onboarding/settings/public footer as required.
- Include accessibility checks for legal links and action controls.

## Acceptance Criteria
1. User can submit export and deletion requests from UI entry points.
2. Policy and terms links are visible where required before pilot launch.
3. UI states correctly reflect pending/success/failure request states.
4. End-to-end flow passes from UI request to backend completion status.

## Validation
- Frontend integration tests for request submission and state display.
- UI acceptance checklist for legal link visibility.
- End-to-end smoke test for both request types.

## Deliverables
- Updated frontend views/components for governance actions.
- Legal links in required product surfaces.
- UI/integration test artifacts and release checklist evidence.
