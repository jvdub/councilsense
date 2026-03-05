# Meeting Summary Gap Report (Baseline vs Current Runtime)

Context analyzed:
- Baseline target: `meeting_minutes_baseline_2024-12-03.md`
- Current runtime observed: `run-latest` on 2026-03-04 for `city-eagle-mountain-ut`, meeting `meeting-79fc77db0c72c89d` (2024-12-03), with published row `pub-local-meeting-79fc77db0c72c89d-00953710`
- Current implementation inspected: `backend/src/councilsense/app/local_pipeline.py`, `backend/src/councilsense/app/summarization.py`, and meeting detail API contract/tests

## What good looks like (from baseline)

- **Summary scope**: concise but broad coverage of major themes (development scale, infrastructure/legal items, governance calendar outcomes).
- **Decisions + actions separation**: clear distinction between approved decisions and procedural follow-up actions.
- **Topics quality**: topic labels are semantic and user-meaningful (e.g., residential growth, open space, right-of-way, interlocal transfer).
- **Evidence linkage**: explicit supporting phrases for major claims, including resolution text and key discussion evidence.
- **Specificity + grounding**: concrete quantities and named entities (e.g., `893 units`, `208 acres`, named presenters, dates).
- **Readability**: structured sections with predictable headings and skimmable bullets.

## Current behavior observed

- Runtime output shape is stable and structured (`summary`, `key_decisions`, `key_actions`, `notable_topics`, `claims` + evidence pointers).
- For the 2024-12-03 meeting, decisions/actions are materially correct and grounded in claims with excerpts.
- Summary text is fluent but partially generic in places and does not consistently preserve baseline-level numeric/detail richness.
- `notable_topics` currently surfaced as `"approved", "purchase", "agreement"` (token-like keywords, not reader-facing topics).
- Evidence pointers are present per claim, but location precision is coarse (`section_ref="artifact.html"`, null char offsets), and there is no separate human-readable “evidence references” section.

## Missing or weak coverage (prioritized)

1. **Topic semantics are weak for end users**
	- Output topics are high-frequency tokens rather than civic concepts.
	- Impact: lowers scan value in reader UI and notifications.

2. **Evidence presentation is underpowered vs baseline style**
	- Claims have excerpts, but no dedicated “key evidence references” block summarizing phrase-level support across the whole summary.
	- Impact: harder to quickly verify non-claim summary statements.

3. **Specificity consistency is not guaranteed**
	- Baseline includes high-value quantitative/context details; current summary may omit these depending on model phrasing.
	- Impact: loss of decision context and policy salience.

4. **Grounding coverage is claim-centric, not summary-centric**
	- Evidence is attached to claim rows only; summary sentences themselves are not validated for coverage.
	- Impact: summary can include broad statements not clearly traceable in output payload.

5. **Readability contract mismatch with baseline artifact**
	- Baseline includes explicit “Evidence References (key phrases)” section and richer topic labels; current contract does not expose equivalent sectioning.
	- Impact: output is technically valid but not aligned with target report style/content.

## Root-cause hypotheses (implementation-level)

- **Topic derivation heuristic is token-frequency-based**
  - In `local_pipeline.py`, `_derive_grounded_sections` builds topics from token counts over decisions/actions, then emits top tokens (max 3).
  - This naturally yields words like “approved/purchase/agreement” instead of semantic civic topics.

- **LLM prompt contract is too narrow**
  - `_summarize_with_ollama` asks only for JSON keys `summary` and `claim`.
  - Decisions/actions/topics are post-derived heuristically, so LLM is not directly producing richer structured sections.

- **Evidence pointer generation is best-match sentence only**
  - `_best_evidence_excerpt_for_finding` picks one sentence by token overlap and stores excerpt; offsets are unset.
  - This limits precision and prevents stronger evidence traceability checks.

- **No explicit extractor for quantitative salient facts**
  - `_build_grounded_summary` prioritizes decision/action keywords but has no dedicated logic to preserve numeric anchors (counts, acreage, dates) when present.

- **Publication/API contract lacks evidence-reference summary field**
  - Current persisted contract supports claims + evidence pointers, but not a separate “evidence references (key phrases)” collection at publication level.

## Acceptance checks (measurable future validation)

1. **Topic quality check**
	- For sampled published meetings, `notable_topics` entries are noun-phrase civic topics (not generic verbs like “approved”).
	- Pass criterion: ≥2 topic entries per meeting are concept-level labels.

2. **Specificity retention check**
	- If source contains quantitative facts (e.g., units/acres/dates), summary or decisions/actions include at least one such fact.
	- Pass criterion: detected quantitative anchors in source have ≥1 reflected anchor in output sections.

3. **Evidence readability check**
	- Meeting detail payload includes a concise, user-readable evidence reference list (or equivalent) beyond per-claim raw pointers.
	- Pass criterion: API/UI can render an “evidence references” block with at least 3 grounded phrases when available.

4. **Grounding coverage check**
	- Every key decision/action sentence has at least one evidence pointer excerpt.
	- Pass criterion: 100% coverage for `key_decisions` + `key_actions` items.

5. **Evidence precision check**
	- Evidence pointers contain either section-level refs with finer granularity than `artifact.html` or valid character offsets where feasible.
	- Pass criterion: ≥80% of pointers have precise locators (granular section_ref or char offsets).

6. **Style parity check vs baseline**
	- Rendered meeting output includes: Summary, Decisions, Actions, Notable Topics, Evidence References.
	- Pass criterion: all five sections present and non-empty for high-confidence publications.
