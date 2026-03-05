# Limited-Confidence Reason Codes and Publish Wiring

**Task ID:** TASK-ST-025-03  
**Story:** ST-025  
**Bucket:** backend  
**Requirement Links:** ST-025 Acceptance Criteria #3 and #4, AGENDA_PLAN §5 Phase 1 — publish continuity, AGENDA_PLAN §8 Risks and mitigations

## Objective
Implement confidence policy wiring that transitions to `limited_confidence` with explicit reason codes for missing, weak, or conflicting source conditions.

## Scope
- Define reason-code taxonomy for missing-source, weak-precision, and unresolved-conflict scenarios.
- Wire confidence evaluation outputs into publish status transitions.
- Ensure publish continuity remains intact for partial-source meetings under downgraded confidence.
- Out of scope: frontend presentation copy and notification channel policy changes.

## Inputs / Dependencies
- TASK-ST-025-01 source-coverage diagnostics.
- TASK-ST-025-02 authority conflict and fallback diagnostics.
- Existing publish status model (`processed`, `limited_confidence`) and persistence hooks.

## Implementation Notes
- Keep reason-code values stable and versioned for downstream analytics and UI consumption.
- Confidence downgrade decisions must be deterministic and replay-safe.
- Avoid introducing suppression behavior for partial-source cases unless explicitly blocked by existing gates.

## Acceptance Criteria
1. Confidence policy emits explicit reason codes for missing, weak, and conflict conditions.
2. Publish transitions to `limited_confidence` when unresolved conflicts/weak precision conditions apply.
3. Partial-source meetings still publish with transparent confidence labeling.
4. Status and reason-code persistence is deterministic across reruns.

## Validation
- Run publish-flow fixtures covering each reason-code path.
- Verify reruns preserve identical status + reason-code outputs.
- Confirm no regression in partial-source publish continuity.

## Deliverables
- Reason-code taxonomy and policy mapping table.
- Publish status decisioning integration updates.
- Replay determinism validation notes for confidence transitions.
