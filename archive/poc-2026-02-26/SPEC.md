# CouncilSense — Specification (Working Draft)

**Status**: Working draft

## 1. Purpose

CouncilSense is a local-first assistant that ingests city council agenda-style packets/minutes (PDF and/or text), summarizes meetings, and highlights items relevant to the user’s interests with evidence.

Initial user interests:

- Mentions of the neighborhood **Sunset Flats**
- **City code / ordinance changes**, with emphasis on residential impacts
- **New laundromats** being proposed/approved

## 2. Goals

- Ingest meeting documents (PDF and/or text) reliably.
- Produce a human-readable meeting summary.
- Produce a “Things you care about” list with:
  - why the item matters (explanation)
  - evidence quotes/snippets (grounded in source text)
  - links to the agenda item(s) or attachment(s)
- Support Q&A over a meeting (and later, across meetings).
- Be auditable: every claim should have traceable evidence.

## 3. Non-Goals (initial MVP)

- Real-time transcription of live meetings.
- Audio/video processing.
- Multi-channel notifications (email/SMS/push) — web-first only.
- Multi-user accounts, logins, roles, or tenant isolation.
- Hosted SaaS deployment concerns (billing, quotas, abuse prevention, data residency).
- Automated scheduled ingestion from arbitrary user-provided URLs (manual import only).
- Fully automated policy analysis or legal advice.

## 4. Key Product Decisions

### 4.1 Web-first interface

- A web UI is the primary interface.
- Notifications and other channels come later.

### 4.2 Local-first by default

- Default operation should work on a single machine.
- Cloud LLMs (e.g., Bedrock) may be optional.

### 4.3 Evidence-first summaries

- The assistant must prefer “I can’t find evidence for that” over speculation.

### 4.4 Personal MVP first

- The MVP is designed to work for a single user on a single machine.
- The system is allowed to be opinionated and simplified (no auth, no multi-tenant data model).
- The design should still keep a clean path to multi-user later by keeping a clear separation between:
  - ingestion/parsing
  - summarization/classification
  - presentation (UI)

## 5. High-Level Architecture

### 5.1 Components

- **Ingestion / Parsing Service (Python)**

  - Extract text and structure from PDFs
  - Build a canonical meeting representation
  - Run summarization + relevance classification pipelines

- **Web App (Next.js)**

  - Upload/ingest meetings
  - Display meeting summaries and highlights
  - Provide a chat interface for Q&A

- **Persistence (initial: SQLite)**
  - Store meetings, agenda items, extracted text, LLM outputs, user interests, feedback

Personal MVP constraints:

- No authentication.
- One local “profile” (interest settings) stored alongside the local database/config.
- Ingestion is initiated manually (upload/select a file), not scheduled.

### 5.2 Data Flow (conceptual)

1. User uploads/points to meeting packet
2. Parser extracts text + structure into canonical JSON model
3. Pipeline summarizes + classifies relevance
4. UI renders results and allows Q&A
5. User feedback updates preferences and improves filtering

## 6. Canonical Data Model (JSON)

TOON is a representation at the LLM boundary; the canonical internal model is JSON.

### 6.1 Meeting

- `meeting_id` (string)
- `source_files[]` (paths/URLs)
- `meeting_date` (optional)
- `location` (optional)
- `agenda_items[]`
- `attachments[]`
- `ingestion_metadata` (extractor used, timestamps, stats)

### 6.2 AgendaItem

- `item_id` (e.g., `14.A`)
- `title`
- `body_text` (normalized)
- `page_range` (optional)
- `sections[]` (optional)

### 6.3 Attachment

- `attachment_id`
- `title` (optional)
- `type_guess` (e.g., `staff_report`, `plat`, `map`, `exhibit`, `policy`)
- `body_text` (normalized)

### 6.4 Highlight (what the user sees)

- `title`
- `category` (e.g., `neighborhood`, `code_change`, `laundromat`)
- `why` (human-readable explanation)
- `confidence` (0..1)
- `evidence[]` (quotes/snippets with source pointers)
- `links` (agenda item IDs / attachment refs)

## 7. Ingestion & Parsing

### 7.1 Inputs

- PDF agenda packet / minutes
- Plain text minutes (optional)

### 7.2 Extraction strategy

- Prefer a single “best” PDF extractor for canonical text.
- Keep other extractor outputs for debugging only.

### 7.3 Structure detection

- Identify agenda item headings (e.g., `14.A. ORDINANCE / PUBLIC HEARING - ...`).
- Separate the “agenda list” from later attachments/exhibits.
- Attempt to classify attachments (heuristics).

### 7.4 Normalization

- Normalize whitespace
- Preserve ordering
- Avoid lossy transformations that harm evidence quoting

## 8. Agent Capabilities

### 8.1 Primary tasks

- Summarize a meeting:
  - overall summary (short)
  - per-agenda-item summaries
- Highlight interest areas:
  - Sunset Flats mentions (why, where, evidence)
  - City code/ordinance changes (which chapter/section, why, evidence)
  - Laundromat proposals/approvals (what is proposed, where, evidence)
- Answer questions grounded in documents:
  - “What happened related to Sunset Flats?”
  - “Which ordinances were on the agenda and what changed?”

### 8.2 Tooling model (agentic behavior)

The assistant should operate as a tool-using agent, not a single giant prompt.

Candidate tools:

- `list_meetings()`
- `get_meeting(meeting_id)`
- `search_meeting_text(meeting_id, query)`
- `get_agenda_item(meeting_id, item_id)`
- `summarize_agenda_item(meeting_id, item_id)`
- `classify_relevance(meeting_id, item_id, interest_profile)`
- `extract_evidence(meeting_id, item_id, claim)`

## 9. Summarization & Relevance Pipeline

Two-pass pipeline (recommended):

### 9.1 Pass A — Agenda item understanding

Input: agenda item (title + body text)
Output (structured):

- `summary` (2–5 bullets)
- `actions` (votes/motions/decisions if present)
- `entities` (places, projects, organizations)
- `citations` (quotes/snippets)

### 9.2 Pass B — Interest classification

Input: Pass A output + interest profile
Output:

- `relevant` (bool)
- `why` (plain language)
- `confidence`
- `evidence` (must include quotes)

### 9.3 Optional Pass C — Meeting-level narrative

Input: all agenda item summaries
Output:

- `meeting_summary`
- `top_highlights`

## 10. Interest Profile (evolvable)

### 10.1 Start simple

- Keyword/heuristic rules for recall-first filtering
- Then LLM-based semantic classification for precision

### 10.2 User controls

- strict vs loose relevance
- thresholds
- mute topics/entities
- “notify on discussion” vs “notify on decision”

## 11. TOON Integration

### 11.1 Recommendation

Use TOON as a **prompt/interchange format at the LLM boundary**, not as the canonical storage format.

### 11.2 Rationale

- Token-efficient and LLM-friendly for large structured context.
- Internal logic, persistence, and APIs remain simpler with JSON.

### 11.3 Pattern

- Canonical: JSON model in code + DB
- LLM input: encode relevant context to TOON
- LLM output: request TOON in a strict template
- Post-process: decode TOON → JSON, validate, retry on failures

### 11.4 Guardrails

- Decode with strict mode (fail fast)
- Require array lengths and explicit field headers where possible
- Require evidence fields for any claim
- Prefer TOON Core Profile (simpler subset) for reliability

## 12. Persistence

### 12.1 Tables/collections (conceptual)

- `meetings`
- `agenda_items`
- `attachments`
- `summaries` (per item + per meeting)
- `highlights`
- `interest_profiles`
- `feedback` (useful/not useful, muted, etc.)

### 12.2 Caching

- Cache LLM outputs by content hash to avoid re-computation.

## 13. UI/UX Requirements (Web)

- Upload/import a meeting packet
- Meeting page:
  - agenda list
  - meeting summary
  - “Things you care about” with evidence
  - “Maybe relevant” (lower confidence)
- Chat panel scoped to:
  - a selected meeting (MVP)
  - later: all meetings

## 14. Evaluation & Quality

- Maintain a small “gold set” of meetings with expected highlights.
- Automated checks:
  - every highlight must include evidence quotes
  - do not claim actions not present in text
- Track regressions when changing prompts, models, or extractors.

## 15. Security & Privacy

- Documents may contain sensitive information.
- Avoid sending raw PDFs to cloud LLMs by default.
- If cloud LLM is enabled:
  - explicit user opt-in
  - minimize data (only relevant chunks)
  - store provider + prompt/version metadata for audit

## 16. Milestones

### M0 — Spike (done)

- Basic extraction + heuristic rule detection + evidence snippets.

### M1 — Canonical MeetingDoc

- Reliable agenda segmentation and attachment handling.

### M2 — LLM summarization (per item)

- Structured outputs with evidence.

### M3 — Relevance highlighting

- Interest profile + semantic classification + confidence.

### M4 — Web UI MVP

- Upload, view meeting, view highlights, basic chat over meeting.

### M5 — Cross-meeting search + notifications

- Search history, saved queries, web notifications.

### M6 — Multi-user (future)

- Add authentication and user profiles.
- Let users register a council source URL and run scheduled ingestion.
- Add tenant isolation and quota/rate limiting.

## 17. User Stories (MVP-oriented)

### Story 1 — Upload & ingest meeting

**As a** user, **I want** to upload a meeting packet PDF, **so that** it can be analyzed.

- Acceptance:
  - Upload succeeds and creates a new `meeting_id`
  - Agenda items appear in UI

### Story 2 — Meeting summary

**As a** user, **I want** a short summary of the meeting, **so that** I can skim quickly.

- Acceptance:
  - Summary includes top items and uses evidence-backed phrasing

### Story 3 — Sunset Flats highlights

**As a** user, **I want** to see why Sunset Flats was mentioned, **so that** I can decide if I should read more.

- Acceptance:
  - Highlight includes a specific explanation (agenda item vs attachment)
  - Includes evidence snippet(s)

### Story 4 — City code change highlights

**As a** user, **I want** to see what code/ordinance is changing and why, **so that** I can track policy changes.

- Acceptance:
  - Identifies ordinance(s) / reading / hearing items when present
  - Provides evidence quotes

### Story 5 — Laundromat alerts

**As a** user, **I want** to be notified when laundromats are proposed or approved, **so that** I can follow that development.

- Acceptance:
  - Avoids false positives from “laundry room” references
  - Provides evidence and the approval context

### Story 6 — Ask questions about the meeting

**As a** user, **I want** to ask questions in chat about the meeting packet, **so that** I can drill into details.

- Acceptance:
  - Answers cite evidence from agenda items/attachments
  - If evidence isn’t found, the assistant says so
