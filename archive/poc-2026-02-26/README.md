# CouncilSense

A local-first AI assistant that watches city council meeting minutes and notifies you when something you care about is discussed.

This repo starts with a small “minutes extraction + alerting” spike so we can validate parsing quality and alert rules before building the full web app.

## What you care about (initial)

- Neighborhood mentions: **Sunset Flats**
- City code changes (especially residential)
- New laundromats being considered/approved

These are configured in `interest_profile.yaml`.

## Quick start (spike)

### 1) Create a virtualenv and install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run the spike

You can run with a plain text minutes file, a PDF, or both:

```bash
python -m minutes_spike \
  --meeting-id 2026-01-09 \
  --text minutes.txt \
  --pdf minutes.pdf \
  --profile interest_profile.yaml \
  --out out/2026-01-09.json
```

You can also **import/store** a meeting packet (A1) into a local meeting folder (original PDF + extracted text + ingestion metadata):

```bash
python -m minutes_spike \
  --pdf "Agenda Packet.pdf" \
  --store-dir out/meetings \
  --import-only
```

### View imported meetings (F1)

After importing at least one meeting into `--store-dir`, you can serve a minimal local web UI that lists imported meetings (backed by a SQLite index stored in the same `--store-dir`):

```bash
python -m minutes_spike \
  --store-dir out/meetings \
  --serve
```

Then open `http://127.0.0.1:8000/`.

From the meetings page you can also upload a PDF to import it (A1).

### Next.js UI (K1)

There is a scaffolded Next.js UI in `councilsense_ui/` that provides:

- meeting list
- meeting detail (summary, highlights, agenda item summaries)
- upload/import

It talks to the local Python backend started with `--serve`.

1. Start the backend:

```bash
python -m minutes_spike --store-dir out/meetings --serve
```

2. Start the Next.js UI (in a second terminal):

```bash
cd councilsense_ui
npm run dev
```

Open `http://localhost:3000/`.

If your backend is not at `http://127.0.0.1:8000`, set:

```bash
export COUNCILSENSE_BACKEND_URL="http://127.0.0.1:8000"
```

### HTTP API (K2)

When running `python -m minutes_spike --store-dir out/meetings --serve`, the backend exposes a small JSON API for the UI:

- `POST /api/import` (multipart form-data: `pdf` required, `text` optional)
- `GET /api/meetings`
- `GET /api/meetings/{meeting_id}` (includes mirrored artifacts when available)
- `POST /api/meetings/{meeting_id}/rerun` (JSON body: `profile`, `summarize_all_items`, `classify_relevance`, `summarize_meeting`)
- `POST /api/meetings/{meeting_id}/chat` (JSON body: `{question: string}`)

If you omit `--meeting-id`, a stable ID is auto-generated from the input file hash.

Output is a JSON file containing:

- extracted text (from text file and/or PDF)
- alert decisions per rule
- evidence snippets with line/offset context

### Optional: summarize agenda items (D1)

You can ask CouncilSense to summarize extracted agenda items (Pass A) using a local Ollama model:

1. Add an `llm:` section to your profile YAML:

```yaml
llm:
  provider: ollama
  endpoint: http://localhost:11434
  model: llama3.2:latest
  timeout_s: 120
```

2. Run with `--summarize-first-item` (quick smoke test) or `--summarize-all-items` (summarize each agenda item):

```bash
python -m minutes_spike \
  --pdf "Agenda Packet.pdf" \
  --profile interest_profile.yaml \
  --summarize-all-items \
  --out out/meeting.json
```

On success, each entry in `agenda_items` includes:

- `summary`: `list[str]` (2–5 bullets)
- `pass_a`: `{summary, actions, entities, key_terms, citations}` (with at least one evidence snippet in `citations`)

On failure, the affected agenda item includes `summary_error` and the process exits non-zero.

### Optional: strict TOON-ish roundtrip at the LLM boundary (C2)

If you want the model interaction to be validated and stored as a strict structured roundtrip, enable `--llm-use-toon`:

```bash
python -m minutes_spike \
  --pdf "Agenda Packet.pdf" \
  --profile interest_profile.yaml \
  --summarize-all-items \
  --llm-use-toon \
  --out out/meeting.json
```

This will:

- Encode the agenda-item context as TOON-ish YAML (YAML for now)
- Ask the model to return ONLY a strict YAML structure
- Decode/validate the output (fails fast if invalid)
- Store the artifacts under `agenda_items[*].llm_roundtrip` (input/output + decoded JSON)

### Optional: classify relevance to your interests (D2)

You can label which agenda items matter to your interest rules (Pass B) and produce a UI-ready `things_you_care_about` list:

```bash
python -m minutes_spike \
  --pdf "Agenda Packet.pdf" \
  --profile interest_profile.yaml \
  --classify-relevance \
  --out out/meeting.json
```

This adds:

- `agenda_items[*].pass_b[rule_id]`: `{relevant, why, confidence, evidence}`
- `things_you_care_about[]`: flattened highlights with evidence + links to either an agenda item or an attachment/exhibit (when the mention comes from supporting materials)

## Gold regression check (H1)

A small “gold set” of sample inputs + expected highlights lives in `gold/`.

Run the basic regression check:

```bash
/home/jtvanwage/councilsense/.venv/bin/python scripts/eval_gold.py
```

### Optional: meeting-level summary (D3)

You can produce a short meeting narrative (Pass C) from the existing outputs:

```bash
python -m minutes_spike \
  --pdf "Agenda Packet.pdf" \
  --profile interest_profile.yaml \
  --summarize-all-items \
  --classify-relevance \
  --summarize-meeting \
  --out out/meeting.json
```

This adds `meeting_summary` with:

- `highlights` (top 3–7, evidence-backed)
- `ordinances_resolutions` (best-effort keyword scan, evidence-backed)
- `watchlist_hits` (counts per interest category)

## Next steps (after spike)

- Add Pass B relevance classification on top of Pass A.
- Build a minimal Next.js UI that shows meetings, alerts, and evidence.
