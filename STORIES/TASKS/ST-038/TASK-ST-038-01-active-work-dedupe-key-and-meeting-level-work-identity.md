# Active-Work Dedupe Key and Meeting-Level Work Identity

**Task ID:** TASK-ST-038-01  
**Story:** ST-038  
**Bucket:** backend  
**Requirement Links:** ST-038 Scope (meeting-level active-work dedupe), ST-038 Acceptance Criteria #1 and #3, FR-3, NFR-1

## Objective

Define the active-work identity and dedupe key for on-demand processing so exactly one active work item exists per discovered meeting.

## Scope

- Define the stable dedupe key for active on-demand work using discovered-meeting source identity.
- Define what counts as active work versus terminal work for dedupe purposes.
- Ensure the identity model composes cleanly with existing run/stage lifecycle records.
- Out of scope: request admission-control thresholds, retry reopening rules, and frontend suppression behavior.

## Inputs / Dependencies

- ST-036 discovered-meeting source identity contract.
- ST-037 processing-request contract.
- Existing processing-run and stage-outcome lifecycle model.

## Implementation Notes

- Favor provider-stable source identity over title/date matching.
- Define active-work scope precisely enough to avoid duplicate queued/in-progress runs.
- Keep the contract observable for audit and integration-test assertions.

## Acceptance Criteria

1. One discovered meeting maps to one active dedupe key for queued/in-progress work. (ST-038 AC #1)
2. The dedupe key integrates with existing pipeline lifecycle records without ambiguous identity joins.
3. Terminal work is excluded from the active-work identity so later requests can be re-evaluated. (supports ST-038 AC #3)

## Validation

- Unit tests for dedupe-key generation and active-work classification.
- Review identity joins against existing run/stage persistence.
- Verify the contract is precise enough for concurrent request handling.

## Deliverables

- Active-work dedupe-key contract.
- Meeting-level work identity integration plan.
- Unit tests for active-vs-terminal identity semantics.
