# CouncilSense — Stories (Personal MVP)

This backlog is derived from SPEC.md and assumes a **single-user, local-first** MVP (no auth, no multi-tenant).

Conventions:

- **Priority**: P0 (must), P1 (should), P2 (nice)
- **Status**: Implemented, Partial, Missing
- **DoD**: Definition of Done

---

## Epic A — Local Ingestion & Canonical MeetingDoc

### A1 — Import a meeting packet (PDF)

**Priority**: P0

**Status**: Implemented

As a user, I want to import a council agenda packet PDF so that it can be analyzed.

**Acceptance**

- I can select/upload a PDF in the web UI.
- A new meeting record is created with a stable `meeting_id`.
- The system stores:
  - the original PDF (or a reference to it)
  - extracted text output
  - ingestion metadata (timestamp, extractor used)

**DoD**

- One-click path from UI to stored meeting.
- Errors are user-readable (e.g., “PDF appears scanned; OCR not supported yet”).

---

### A2 — Extract text from PDF reliably (single canonical extractor)

**Priority**: P0

**Status**: Implemented

As a user, I want consistent text extraction so that summaries and evidence quotes are stable across runs.

**Acceptance**

- The system uses one chosen primary extractor for canonical text.
- If extraction fails, the system returns a clear failure reason.
- Extraction output is normalized (whitespace cleanup) without destroying ordering.

**DoD**

- Same PDF produces deterministic extracted text (modulo library version changes).

---

### A3 — Detect agenda items from agenda-style packets

**Priority**: P0

**Status**: Implemented

As a user, I want the meeting’s agenda items identified so that summaries and highlights can be organized by agenda item.

**Acceptance**

- The system extracts a list of agenda item headers (e.g., `14.A`, title).
- Each agenda item has a `title` and some associated `body_text` (even if approximate).
- The system avoids obvious false positives from attachments (policies/definitions).

**DoD**

- Agenda list renders in the UI for the imported meeting.

---

### A4 — Identify attachments/exhibits and classify type (heuristics)

**Priority**: P1

**Status**: Implemented

As a user, I want the system to recognize when a mention comes from an attachment (e.g., a plat) so that “why mentioned” is correctly explained.

**Acceptance**

- The system can label evidence as coming from:
  - an agenda item OR
  - an attachment/exhibit bucket
- For common patterns, assign `type_guess` such as `plat`, `staff_report`, `policy`, `map`.

**DoD**

- Mentions like “Sunset Flats” found inside plats are explained as attachments.

**Implementation notes (spike)**

- Import stores `attachments.json` alongside `agenda_items.json`, and `meeting.json` includes an `attachments` artifact pointer (`stored_path`, `count`, `source`).
- CLI output includes a top-level `attachments[]` preview (id/title/type_guess/body_text).
- Each evidence snippet in `rule_results[].evidence[]` may include:
  - `bucket`: `agenda_item` or `attachment`
  - `agenda_item`: `{item_id, title}` when bucketed as an agenda item
  - `attachment`: `{attachment_id, title, type_guess}` when bucketed as an attachment
- Each rule result also includes `attachment_refs[]` (parallel to `agenda_refs[]`) for easy UI linking.

---

## Epic B — Interest Profile (Personal)

### B1 — Maintain a single local interest profile

**Priority**: P0

**Status**: Implemented (but see M1: --init-profile template YAML is currently invalid)

As a user, I want to configure what I care about (Sunset Flats, code changes, laundromats) so that the system can highlight relevant items.

**Acceptance**

- There is a single “local profile” stored in a config file or DB.
- The profile supports:
  - neighborhood terms
  - code-change signals
  - laundromat terms + approval context
- Profile edits do not require code changes.

**DoD**

- Changing the profile changes the highlights for the same meeting.

---

### B2 — Fast prefiltering (keywords/heuristics)

**Priority**: P0

**Status**: Implemented

As a user, I want cheap keyword filtering to narrow what the LLM sees, so that analysis is faster and cheaper.

**Acceptance**

- The system can flag candidate agenda items/attachments using keyword/context rules.
- The system outputs evidence snippets for each hit.

**DoD**

- Prefilter output is stored and viewable.

---

## Epic C — LLM Boundary + Structured Outputs (TOON-compatible)

### C1 — Add an LLM provider abstraction (Ollama first)

**Priority**: P0

**Status**: Implemented

As a user, I want the system to call a local LLM so that it can summarize agenda items.

**Acceptance**

- LLM calls are behind a provider interface.
- Provider config is local (model name, endpoint).
- Errors are captured and shown (timeouts, model missing).

**DoD**

- One agenda item can be summarized via the provider.

---

### C2 — Encode meeting context for the LLM (JSON canonical, TOON at boundary)

**Priority**: P1

**Status**: Implemented (TOON-ish YAML roundtrip + strict decode)

As a user, I want the model to receive structured context efficiently so that it can answer accurately with fewer tokens.

**Acceptance**

- Internally, the app uses a canonical JSON model.
- At the LLM boundary, the system can:
  - encode JSON → TOON for prompts (optional at first)
  - request TOON output for structured results
  - decode TOON → JSON strictly (fail fast)

**DoD**

- A single prompt/response round-trip can be validated and stored.

---

## Epic D — Summarization Pipeline

### D1 — Summarize each agenda item (Pass A)

**Priority**: P0

**Status**: Implemented

As a user, I want a short summary per agenda item so that I can skim the meeting quickly.

**Acceptance**

- For each agenda item, generate:
  - 2–5 bullet summary
  - any detected actions (e.g., ordinance/public hearing, approvals)
  - extracted entities and key terms
- The summary must include at least one evidence quote/snippet.

**DoD**

- Summaries are stored and displayed under each agenda item.

---

### D2 — Classify relevance to my interests (Pass B)

**Priority**: P0

**Status**: Implemented (heuristic rules; semantic/LLM precision is tracked in J1)

As a user, I want the system to label which agenda items matter to my interests, so that I can focus only on what I care about.

**Acceptance**

- For each agenda item (or candidate set), produce:
  - `relevant` boolean per interest category
  - `why` explanation
  - `confidence`
  - evidence quotes/snippets
- The classifier must not claim facts without evidence.

**DoD**

- “Things you care about” section renders from these results.

---

### D3 — Meeting-level summary (Pass C)

**Priority**: P1

**Status**: Implemented (heuristic meeting summary)

As a user, I want a meeting-level summary so that I can understand the meeting without opening each item.

**Acceptance**

- Produce a short meeting narrative:
  - top 3–7 highlights
  - any important ordinances/resolutions
  - a “watchlist hits” section

**DoD**

- Meeting page has a top summary section.

---

## Epic E — Evidence & Auditability

### E1 — Evidence citations for every highlight

**Priority**: P0

**Status**: Implemented

As a user, I want every highlight to include evidence so that I can trust it.

**Acceptance**

- Each highlight includes 1–3 evidence snippets with source pointers (agenda item ID or attachment).
- If evidence isn’t found, the highlight is not produced (or is flagged as low confidence with explanation).

**DoD**

- UI displays evidence inline and allows expanding the surrounding text.

---

### E2 — Provenance tracking for LLM outputs

**Priority**: P1

**Status**: Implemented

As a user, I want to know which model/prompt produced a result so that behavior is reproducible.

**Acceptance**

- Store model name/version, prompt template version, and timestamp with outputs.

**DoD**

- A stored summary can be traced to its generation settings.

---

## Epic F — Web UI (Personal MVP)

### F0 — Upload/import meeting packet in the web UI

**Priority**: P0

**Status**: Implemented

As a user, I want to upload/import a meeting packet from the web UI so that I don’t have to use the CLI to ingest meetings.

**Acceptance**

- The meeting list page includes an upload form for a PDF (and optionally a text minutes file).
- Submitting the form:
  - stores the file(s) under the configured `--store-dir`
  - creates a stable `meeting_id`
  - writes `ingestion.json` and `meeting.json` in the meeting folder
- On success, the UI redirects to the meeting detail page.
- On failure (e.g., scanned PDF / no extractable text), the UI shows a user-readable error.

**DoD**

- One-click path from browser → stored meeting folder → visible in meeting list.

---

### F1 — Meeting list page

**Priority**: P0

**Status**: Implemented

As a user, I want to see a list of imported meetings so that I can navigate my history.

**Acceptance**

- Shows meeting date/title (best-effort) and import timestamp.
- Clicking opens a meeting detail page.

**DoD**

- Works with local SQLite persistence.

---

### F2 — Meeting detail page

**Priority**: P0

**Status**: Implemented

As a user, I want a meeting page with agenda items and highlights so that I can review what matters.

**Acceptance**

- Shows meeting-level summary (if available).
- Shows “Things you care about” section with evidence.
- Shows agenda items list with per-item summaries.

**DoD**

- The page is usable without reading raw extracted text.

---

### F3 — Manual re-run analysis

**Priority**: P1

**Status**: Implemented

As a user, I want to re-run analysis after changing my profile or model so that results update.

**Acceptance**

- “Re-run analysis” button exists.
- It invalidates/updates stored results deterministically.

**DoD**

- Re-run produces updated highlights.

---

### F4 — Configure store directory in the UI

**Priority**: P1

**Status**: Implemented

**Why Partial**: (resolved)

As a user, I want the web UI to clearly show which store directory it’s using so that I don’t accidentally import meetings into an unexpected folder.

**Acceptance**

- The UI shows the absolute `store_dir` path.
- If the server starts without a valid writable store dir, the UI shows a clear error.

**DoD**

- No “silent success” importing to the wrong location.

---

## Epic G — Q&A (Agent Interface)

### G1 — Chat scoped to one meeting

**Priority**: P1

**Status**: Implemented (narrow intent: evidence-first search, optimized for “why mentioned”)

As a user, I want to ask questions about a single meeting packet so that I can drill into details.

**Acceptance**

- Chat is scoped to a selected meeting.
- Agent uses tools:
  - search meeting text
  - fetch agenda items
  - quote evidence
- Agent answers must include evidence or say “not found”.

**DoD**

- Can answer: “Why was Sunset Flats mentioned?” and cite the attachment evidence.

---

### G2 — Evidence-first Q&A beyond “why mentioned”

**Priority**: P1

**Status**: Implemented

As a user, I want to ask broader questions about a meeting (ordinances, decisions, projects) so that I can understand outcomes without manually searching the packet.

**Acceptance**

- Questions like these work (at least best-effort):
  - “Which ordinances were on the agenda and what changed?”
  - “What was decided about laundromats?”
  - “What happened related to Sunset Flats?”
- Answers:
  - cite evidence snippets and point back to agenda item IDs and/or attachments
  - say “not found” when evidence is absent

**DoD**

- Chat responses are grounded and navigable (links/IDs), not just generic summaries.

---

## Epic H — Evaluation & Quality

### H1 — Maintain a small gold set

**Priority**: P2

**Status**: Implemented

As a developer, I want a small set of meeting packets and expected highlights so that changes can be regression-tested.

**Acceptance**

- A folder of sample inputs (or references) exists.
- A simple script can evaluate whether highlights contain expected keywords/evidence.

**DoD**

- Basic regression check runs locally.

---

## Epic I — Persistence & Caching

### I1 — Persist analysis outputs in SQLite (not just files)

**Priority**: P1

**Status**: Implemented

As a user, I want meeting analysis results stored in a local database so that the UI can query and render data without re-reading many JSON files.

**Acceptance**

- SQLite stores (at minimum):
  - meetings index (already)
  - agenda items
  - attachments
  - Pass A summaries
  - Pass B per-rule results + flattened highlights
  - Pass C meeting summary
- The canonical “meeting folder on disk” remains the source of truth for raw artifacts, but the DB mirrors enough fields for UI queries.

**DoD**

- Meeting list/detail pages can be rendered from DB queries with minimal filesystem reads.

---

### I2 — Cache LLM outputs by content hash

**Priority**: P1

**Status**: Implemented

As a user, I want summarization/classification to avoid re-calling the LLM when inputs haven’t changed so that re-runs are fast and cheap.

**Acceptance**

- For each agenda item, compute a stable input hash (title + body text + prompt template id/version + model identity).
- If the hash matches a prior stored result, skip the LLM call and reuse the cached output.
- Cache entries include provenance and can be invalidated when:
  - model changes
  - prompt template version changes
  - the source text changes

**DoD**

- Re-running Pass A on an unchanged meeting performs near-zero LLM calls.

---

## Epic J — Semantic Relevance (beyond heuristics)

### J1 — Pass B semantic classification (LLM) for precision

**Priority**: P1

**Status**: Implemented

As a user, I want relevance classification to be semantic (not just keyword hits) so that I get fewer false positives while still seeing real issues.

**Acceptance**

- Pipeline:
  - Use B2 prefilter for recall (cheap rules)
  - Then run an LLM classifier on the candidate agenda items/attachments for precision
- For each interest category, the classifier returns:
  - `relevant`, `why`, `confidence`
  - 1–3 evidence snippets (direct quotes) tied to an agenda item or attachment
- Outputs are stored with provenance (model + prompt template version).

**DoD**

- A “laundromat” false positive like “laundry room” is rejected by the semantic pass.

---

## Epic K — Next.js Web App (SPEC-aligned)

### K1 — Scaffold Next.js UI (meeting list + detail + upload)

**Priority**: P1

**Status**: Implemented

As a user, I want a modern web UI (Next.js) that supports upload and browsing so that CouncilSense matches the SPEC’s web-first direction.

**Acceptance**

- Next.js app has:
  - upload/import page
  - meeting list
  - meeting detail (summary, highlights, agenda item summaries)
- Local-first: no auth.

**DoD**

- End-to-end upload → view meeting → view highlights works via a local backend.

---

### K2 — Define a minimal HTTP API for the UI

**Priority**: P1

**Status**: Implemented

As a developer, I want a stable local HTTP API so that the Next.js UI can call ingestion, listing, rerun, and chat without tight coupling to filesystem layout.

**Acceptance**

- Provide endpoints for:
  - import/upload
  - list meetings
  - get meeting detail (including artifacts)
  - rerun analysis
  - chat over a meeting
- Responses are JSON, include useful error messages, and preserve evidence pointers.

**DoD**

- The UI no longer needs to scrape HTML or read raw files.

---

## Epic L — Meeting Metadata Extraction

### L1 — Extract meeting date and location from packet text

**Priority**: P2

**Status**: Implemented

As a user, I want the meeting date and location shown in the UI so that I can quickly identify meetings.

**Acceptance**

- Best-effort heuristics extract:
  - date (if present)
  - location (if present)
- Extracted metadata is stored with the meeting and shown in the meeting list/detail pages.

**DoD**

- Imported meetings show a meaningful date even when the meeting_id is hash-based.

---

## Epic M — Hardening / Paper Cuts

### M1 — Fix `--init-profile` to generate valid YAML

**Priority**: P0

**Status**: Missing (bugfix)

As a user, I want `--init-profile` to create a valid profile file so that setup works without manual edits.

**Acceptance**

- The generated profile file parses with `yaml.safe_load`.
- The file uses spaces (no tab indentation).
- The generated profile includes the three initial interest rules.

**DoD**

- `python -m minutes_spike --init-profile` creates a usable profile and the next run can load it.

---

## Future (Out of MVP Scope)

- Multi-user accounts and user-managed council URLs
- Scheduled ingestion and notifications (email/SMS/push)
- OCR for scanned PDFs
- Cross-meeting semantic search and long-term trend analysis
