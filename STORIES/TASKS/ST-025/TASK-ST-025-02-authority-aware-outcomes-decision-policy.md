# Authority-Aware Outcomes Decision Policy

**Task ID:** TASK-ST-025-02  
**Story:** ST-025  
**Bucket:** backend  
**Requirement Links:** ST-025 Acceptance Criteria #2, AGENDA_PLAN §3 Target architecture (authority policy), AGENDA_PLAN §8 Risks and mitigations (source conflict risk)

## Objective
Implement authority-aware extraction policy that prefers minutes-aligned evidence for final decisions/actions when minutes are available.

## Scope
- Define authority precedence rules for outcomes extraction (minutes > agenda/packet for decisions/actions).
- Add conflict detection hooks when supplemental sources disagree with minutes.
- Define fallback behavior when minutes are absent and only agenda/packet sources exist.
- Out of scope: publish-state reason-code taxonomy and final limited-confidence transitions.

## Inputs / Dependencies
- TASK-ST-025-01 deterministic compose assembly.
- ST-005 evidence-grounded summarization extraction behavior.
- ST-024 canonical source metadata including document kind and authority attributes.

## Implementation Notes
- Keep policy deterministic and explainable through structured diagnostics.
- Distinguish contradiction vs supplemental detail to avoid over-downgrading confidence.
- Ensure outcomes extraction preserves publish continuity under missing-minutes conditions.

## Acceptance Criteria
1. Decisions/actions prefer minutes-aligned evidence when minutes are present.
2. Contradictions between authoritative and supporting sources are explicitly flagged.
3. Fallback behavior for no-minutes meetings is defined and deterministic.
4. Policy outputs include structured diagnostics consumed by confidence decisioning.

## Validation
- Execute fixtures where minutes agree/disagree with agenda/packet and verify precedence.
- Verify fallback extraction when minutes are absent.
- Confirm policy diagnostics are stable and machine-consumable.

## Deliverables
- Authority policy specification for outcomes extraction.
- Conflict signal contract for downstream confidence logic.
- Fallback rule matrix for partial-source conditions.
