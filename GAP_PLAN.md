# GAP_PLAN — One-Page Execution Checklist

## Objective

Reach baseline parity for meeting quality while keeping architecture unchanged and API contract backward compatible.

## Scope

- Files: `backend/src/councilsense/app/local_pipeline.py`, `backend/src/councilsense/app/summarization.py`, meeting detail shaping, `backend/tests/`
- Constraints: additive/reversible changes only; no new services/datastores; no breaking API changes

## Parity Targets (must all pass on fixtures)

- [ ] Required sections non-empty: `summary`, `key_decisions`, `key_actions`, `notable_topics`, `evidence_references` (when evidence exists)
- [ ] Topic quality: concept-level civic phrases; reject generic-only tokens (e.g., approved/agreement)
- [ ] Specificity retention: if source has quantitative anchors (units/acres/dates/counts), at least one appears in summary or decisions/actions
- [ ] Grounding coverage: 100% of decisions/actions have ≥1 evidence pointer
- [ ] Evidence usability: ≥3 deduplicated reader-usable evidence references when available
- [ ] Evidence precision: majority of pointers are finer than file-level when technically possible

## Fixture + Scorecard

- [ ] Fixture set includes: 2024-12-03 Eagle Mountain + 2 structurally different meetings
- [ ] Per run scorecard records: section completeness, topic semantics, specificity, grounding coverage, evidence count/precision
- [ ] Scorecard artifact saved per run (JSON or markdown)

## Phase Checklist

### Phase 0 — Rubric Freeze (no behavior change)

- [ ] Codify checks in tests/helpers
- [ ] Capture pre-change baseline scores
- [ ] Centralize thresholds in test constants
- **Go/No-Go:** checks are repeatable and stable across reruns

### Phase 1 — Contract Safety (additive payload)

- [ ] Expose additive `evidence_references` in meeting detail payload
- [ ] Keep existing fields unchanged
- [ ] Add contract tests for presence/non-empty behavior by evidence availability
- **Go/No-Go:** compatibility tests green; existing consumers unchanged

### Phase 2 — Topic Semantics Hardening

- [ ] Derive phrase-level topics from decisions/actions/claims
- [ ] Add suppression list for low-information tokens
- [ ] Normalize to 3–5 civic concept labels
- [ ] Ensure each topic maps to supporting evidence
- **Go/No-Go:** topic semantic thresholds pass on all fixtures

### Phase 3 — Specificity + Evidence Hardening

- [ ] Add quantitative-anchor harvesting (units/acres/dates/counts/entities)
- [ ] Enforce anchor carry-through into summary or decisions/actions when present
- [ ] Build deterministic `evidence_references` projection (dedupe + rank)
- [ ] Improve locator precision (subsection/offset) where parser supports it
- **Go/No-Go:** specificity + evidence thresholds pass; decision/action grounding remains 100%

### Phase 4 — Enforcement + Rollout

- [ ] Add flags: topic hardening, specificity retention, evidence projection
- [ ] Start report-only shadow gates
- [ ] Promote to enforced gates after 2 consecutive green fixture runs
- [ ] Roll out by environment/cohort
- **Go/No-Go:** Gate A + B + C all green

## Gate Matrix (release requires all green)

- **Gate A — Contract Safety:** additive payload verified, backward-compat tests pass
- **Gate B — Quality Parity:** section completeness + topic semantics + specificity + grounding/evidence thresholds pass
- **Gate C — Operational Reliability:** no significant publish/pipeline regression; deterministic fixture reruns; local/staging smoke green

## Test Strategy (required)

- [ ] Unit: topic normalization/suppression, anchor detection, evidence dedupe/ranking, sparse/duplicate edge cases
- [ ] Integration: end-to-end fixture checks for parity targets
- [ ] Live-smoke: `run-latest` fixture path and scorecard delta vs baseline

## Rollback (if any gate regresses)

- [ ] Disable flags in reverse: specificity → evidence projection → topic hardening
- [ ] Return gates to report-only mode
- [ ] Preserve scorecards and diagnostics for retuning

## Ownership + Cadence

- [ ] Weekly checkpoint: pipeline owner (scorecard deltas), API/frontend owner (compatibility), QA owner (fixture/smoke reliability), tech lead (go/no-go)

## Definition of Done

- [ ] Parity targets pass on fixture set
- [ ] Gates enforced in CI
- [ ] Live-smoke stable with no meaningful reliability regression
- [ ] Rollback path proven without breaking consumers
