# ST-010 Operator Triage View

Use the operator triage script to get a machine-readable view of:

- stale sources,
- failing sources,
- `manual_review_needed` processing runs with provenance metadata.

## Usage

```bash
cd backend
python -m councilsense.app.operator_triage \
  --db /path/to/councilsense.db \
  --stale-before "2026-02-26 00:00:00" \
  --manual-review-limit 100
```

Output is compact JSON with top-level keys:

- `generated_at`
- `stale_before`
- `stale_sources`
- `failing_sources`
- `manual_review_runs`
