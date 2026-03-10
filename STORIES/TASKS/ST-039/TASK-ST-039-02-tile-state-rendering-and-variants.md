# Tile State Rendering and Variants

**Task ID:** TASK-ST-039-02  
**Story:** ST-039  
**Bucket:** frontend  
**Requirement Links:** ST-039 Acceptance Criteria #1 and #2, FR-4, NFR-2

## Objective

Implement meeting tile variants that clearly communicate unprocessed, queued, processing, processed, and failed states.

## Scope

- Create tile-state rendering rules and visual variants for each supported processing state.
- Render state-appropriate affordances for metadata, status labels, and calls to action.
- Preserve empty and error-state behavior for the meetings page.
- Out of scope: request-action wiring, backend state transitions, and live polling.

## Inputs / Dependencies

- TASK-ST-039-01 page data model and API contract integration.
- Existing meetings list visual patterns from ST-007.

## Implementation Notes

- Keep state rendering deterministic and easy to scan.
- Preserve the processed-meeting path to detail without forcing every state into a link.
- Avoid presenting backend-specific jargon like run IDs or queue internals.

## Acceptance Criteria

1. Each meeting tile renders a clear state-specific variant. (ST-039 AC #2)
2. Processed meetings retain a clear route to detail, while non-processed states show appropriate affordances. (ST-039 AC #4)
3. Empty and error-state rendering still works with the expanded explorer behavior.

## Validation

- Component tests for all five tile states.
- Visual/state regression checks for empty and error cases.
- Verify processed-tile navigation remains intact.

## Deliverables

- Meeting tile component variants for all supported states.
- State-to-CTA rendering rules.
- Component tests for tile-state mapping.
