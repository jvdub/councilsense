# 1) Executive summary

CouncilSense should implement agenda + packet + minutes support as an extension of the current modular monolith, not a rewrite. The MVP path is to keep minutes authoritative for outcomes, add agenda/packet as contextual and evidentiary inputs, and ship a clean document-aware v1 contract. Delivery should proceed in phased gates: first deterministic multi-source ingestion and publish continuity, then evidence precision and authority alignment, then rollout hardening (report-only to enforced) with clear rollback switches.

This plan prioritizes:

- clean v1 contracts first, with optional compatibility shims where low-effort,
- deterministic idempotent ingestion per city/meeting/source,
- evidence-grounded quality gates with limited-confidence fallback (not silent failure),
- practical operations (metrics, DLQ, replay, runbooks),
- MVP-first delivery with explicit phase-1.5 hardening path.

---

# 2) Scope and non-goals

**Scope**

- Ingest and correlate agenda, packet, and minutes artifacts for a single meeting.
- Persist multi-artifact lineage and extraction provenance.
- Generate one meeting publication with source-aware evidence pointers.
- Deliver planned/outcomes structures in the reader; add compatibility mapping only if low effort.
- Add source-aware quality diagnostics and phased gate enforcement controls.
- Add operational support for retries, terminal failure classification, DLQ visibility, and replay.

**Non-goals (MVP)**

- No new standalone reader surfaces or new channels.
- No broad UX redesign; only additive meeting-detail enhancements.
- No speculative predictions or policy recommendations.
- No destructive schema changes or forced client migration.
- No OCR-heavy recovery guarantees beyond current parser capabilities.

---

# 3) Target architecture (ingestion, normalization/storage, summarization, API, frontend)

**Ingestion**

- Move from single-source selection to meeting bundle planning per city run.
- For each meeting candidate, resolve expected source types (minutes, agenda, packet), then ingest each source independently.
- Use source-scoped idempotency keys and checksum dedupe to prevent duplicate artifacts and duplicate stage outcomes.

**Normalization/storage**

- Persist canonical meeting documents by kind and revision.
- Persist physical/derived artifacts per document (raw and normalized forms).
- Persist citation-ready spans/sections with stable section paths and optional offsets.
- Persist source-coverage summaries per publication for quality and observability.

**Summarization**

- Compose a structured, multi-document context before summarization.
- Authority policy: minutes authoritative for final decisions/actions; agenda/packet are supporting unless minutes unavailable.
- Emit claim-level evidence with precision ranking (offset > span > section > file).
- On unresolved source conflicts or weak precision, publish limited-confidence with explicit reason codes.

**API**

- Preserve existing meeting detail/list fields and semantics.
- Add optional planned/outcomes blocks and mismatch summaries as additive fields.
- Add evidence v2 fields for document kind, section path, page/offset, precision, and confidence while keeping legacy evidence fields.

**Frontend**

- Keep existing meeting detail route.
- Add optional two-phase rendering: Planned (agenda+packet) and Outcomes (minutes).
- Show compact mismatch signals only when evidence-backed.
- Fall back cleanly to current rendering when additive fields are absent.

---

# 4) Data model and contract changes (v1-first)

**Additive data model**

- Add canonical document entities per meeting: kind, revision, authority metadata, parser metadata, extraction status/confidence.
- Add artifact entities per canonical document for raw/normalized payloads and checksums.
- Add span entities with section path/page/offset metadata for citation precision.
- Extend claim evidence records with optional canonical document/span references and precision metadata.
- Extend summary/publication records with source-coverage and citation-precision aggregates.
- Add pipeline stage DLQ and replay audit tables for terminal failures outside notifications.

**Contract strategy (ship-first, compatibility optional)**

- Define a clean v1 payload centered on planned, outcomes, and planned_outcome_mismatches.
- Adopt evidence_references_v2 as the primary evidence shape.
- Keep publish status model (processed, limited_confidence) with richer reason-code detail.
- If needed, provide temporary compatibility mapping for legacy fields; treat this as non-blocking.

---

# 5) Phased delivery plan with dependencies and acceptance criteria

## Phase 0 — Contract and schema freeze (Week 1)

**Dependencies:** none  
**Deliverables:**

- Canonical document + evidence v2 contract spec.
- Idempotency key spec per stage.
- Rollout flag matrix and rollback sequence.

**Acceptance criteria:**

- Approved v1 schema and API fixtures.
- Compatibility shim scope documented (if required), but not a release blocker.

## Phase 1 — MVP multi-source ingestion and publish continuity (Weeks 2–3)

**Dependencies:** Phase 0  
**Deliverables:**

- Meeting bundle planner (minutes/agenda/packet).
- Source-scoped ingest and extraction with checksum dedupe.
- Existing summarize/publish flow fed by minutes-first + supplemental context.
- Limited-confidence reasoning for missing/weak sources.

**Acceptance criteria:**

- Deterministic rerun produces no duplicate meeting/artifact/publication.
- Pilot city processes meetings with minutes + at least one supplemental artifact.
- Reader delivers planned/outcomes sections from v1 contract.

## Phase 2 — Canonical document spans + evidence precision (Weeks 4–5)

**Dependencies:** Phase 1  
**Deliverables:**

- Canonical document and span persistence.
- Claim evidence linked to document/span references.
- Precision ladder and deterministic evidence ordering.
- Additive evidence v2 projection.

**Acceptance criteria:**

- Evidence ordering stable across reruns.
- Majority of references exceed file-level precision where extractable.
- Evidence v2 contract is stable and documented.

## Phase 3 — API/frontend additive planned/outcomes + mismatches (Weeks 6–7)

**Dependencies:** Phase 2  
**Deliverables:**

- Additive API fields for planned/outcomes and mismatch records.
- Frontend split sections behind flags with fallback behavior.
- Optional mismatch deep-link support.

**Acceptance criteria:**

- Flag-off behavior identical to baseline.
- Flag-on renders planned/outcomes and mismatch states correctly.
- No regression in meeting detail latency beyond agreed budget.

## Phase 4 — Hardening: quality gates, retries, DLQ/replay, alerts (Weeks 8–10)

**Dependencies:** Phase 3  
**Deliverables:**

- Source-aware retry classification and bounded attempts.
- Pipeline DLQ + replay tooling with audit.
- Document-aware gate dimensions (authority alignment, document coverage balance).
- Shadow to enforced rollout controls and rollback drills.

**Acceptance criteria:**

- Two consecutive green report-only runs before each enforcement promotion.
- Replay is idempotent and actor-audited.
- Rollback restores baseline publish behavior without destructive migrations.

---

# 6) Testing and validation plan

- Unit tests: bundle planning, source precedence, idempotency keys, retry classification, precision ranking, conflict handling.
- Integration tests: partial-source meetings, full-source meetings, terminal stage failures to pipeline DLQ, replay no-op safety, publish transaction atomicity.
- Contract tests: v1 API snapshots and schema invariants; legacy compatibility tests optional and non-blocking.
- Frontend tests: additive-field parsing, fallback rendering, planned/outcomes rendering, mismatch empty/neutral/high-severity states.
- End-to-end smoke: scheduled ingest → extract → summarize → publish → reader retrieval for pilot city.
- Non-functional checks: p95 ingest-to-publish latency, queue lag under retry load, parser drift synthetic regression checks.

---

# 7) Observability, operations, and runbook updates

- Extend structured logs with city_id, meeting_id, run_id, stage, source_type, artifact_id, bundle_id, dedupe_key, outcome.
- Add metrics for source ingest/extract outcomes, compose outcomes, coverage ratio, citation precision ratio, authority-alignment violations, pipeline DLQ backlog/age.
- Add alerts for:
  - missing-minutes-with-supplemental-source surge,
  - parser drift by document kind,
  - compose/summarize failure rate spikes,
  - DLQ backlog and stale source freshness.
- Update existing runbooks (health/confidence policy, observability contract, triage, DLQ/replay, alerting, quality rollout) with document-aware triage and rollback steps.
- Require operator replay actions to capture actor, reason, idempotency key, and outcome.

---

# 8) Risks and mitigations

- **Source conflict risk:** agenda/packet may contradict minutes.  
  **Mitigation:** enforce authority alignment; publish minutes-aligned outcomes; flag conflicts and downgrade confidence when unresolved.
- **Parser drift risk:** packet formats may degrade extraction.  
  **Mitigation:** parser version telemetry, drift alerts, staged threshold tightening, fallback to lower-confidence publication.
- **Latency risk:** large packet processing can inflate p95.  
  **Mitigation:** bounded stage budgets, retry caps, decomposition by source, progressive optimization.
- **Contract churn risk:** early v1 fields may need reshaping as real data arrives.  
  **Mitigation:** freeze v1 fixtures at Phase 0, version intentionally when needed, and use optional shims only for short-lived transitions.
- **Operational overload risk:** more stages increase incident volume.  
  **Mitigation:** source-scoped dashboards, clear DLQ ownership, replay automation, runbook drills.

---

# 9) Timeline and staffing estimate

**Estimated duration:** 10 weeks total (MVP usable by end of Week 3; hardening through Week 10)

**Staffing (recommended)**

- 1 backend lead (pipeline contracts, data model, quality gates)
- 1 backend engineer (parsers/extraction, composition, API)
- 1 frontend engineer (meeting detail additive UX)
- 0.5 reliability engineer (metrics/alerts/DLQ/runbooks)
- 0.5 QA/automation engineer (fixtures, integration/e2e)

**Milestones**

- Week 1: contract/schema freeze
- Weeks 2–3: MVP ingest + publish continuity in pilot city
- Weeks 4–5: canonical spans + precision evidence
- Weeks 6–7: additive API/frontend planned-outcomes UX
- Weeks 8–10: retries/DLQ/replay + gated enforcement + rollback validation

---

# 10) Decision log and open questions

## Decision log

1. Minutes are authoritative for final decisions/actions when available.
2. API prioritizes a clean v1 contract; compatibility mappings are optional and non-blocking.
3. Evidence precision is phased, not all-at-once enforcement.
4. Publish policy prefers limited_confidence over silent suppression for partially grounded outputs.
5. Rollout is flag-driven and reversible in this order: notifications/features → UI mismatch sections → split planned/outcomes view → additive API fields (schema stays).

## Open questions

| ID          | Question                                                                                          | Owner                               | Due Date   | Status | Blocker Status | Rollout Control Link                                                              |
| ----------- | ------------------------------------------------------------------------------------------------- | ----------------------------------- | ---------- | ------ | -------------- | --------------------------------------------------------------------------------- |
| ST022-OQ-01 | Should packet table extraction be modeled at row-level in MVP or deferred to hardening?           | Backend Lead (Pipeline)             | 2026-03-11 | Open   | non-blocking   | Keep `st022_gate_mode=report_only` until decision ratified                        |
| ST022-OQ-02 | What exact threshold defines high-severity mismatch notifications?                                | Product Owner + Notifications Owner | 2026-03-12 | Open   | non-blocking   | `st022_notifications_mismatch_enabled` remains off in staging/prod until approved |
| ST022-OQ-03 | Should mismatch comparison be limited to decisions/actions initially or include full claim graph? | Product Owner + Backend Lead        | 2026-03-13 | Open   | non-blocking   | Restrict `st022_ui_mismatch_signals_enabled` rollout to internal/pilot scope      |
| ST022-OQ-04 | What pilot backfill window is required (for example, last 12 vs 24 months)?                       | Data Platform Owner                 | 2026-03-14 | Open   | non-blocking   | Gate broad cohort expansion tied to `st022_schema_additive_writes_enabled`        |
| ST022-OQ-05 | Which source-specific latency/error budgets are acceptable before automatic rollback triggers?    | SRE / Release Owner                 | 2026-03-15 | Open   | non-blocking   | Promotion/rollback thresholds bound to `st022_gate_mode` controls                 |
