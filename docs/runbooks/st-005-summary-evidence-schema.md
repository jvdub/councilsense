# ST-005 Summary/Evidence Persistence Schema Note

This note documents the additive persistence contract introduced for ST-005 Task 01.

## Summary publication record

Table: `summary_publications`

- `publication_status`: `processed` or `limited_confidence`
- `confidence_label`: `high`, `medium`, `low`, or `limited_confidence`
- `summary_text`: rendered summary body
- `key_decisions_json`: JSON array payload for key decisions
- `key_actions_json`: JSON array payload for key actions
- `notable_topics_json`: JSON array payload for notable topics
- `processing_run_id`: optional pointer to `processing_runs.id`
- `publish_stage_outcome_id`: optional pointer to `processing_stage_outcomes.id`
- `version_no`: append-only publication version per meeting

## Claim evidence pointers

Tables: `publication_claims`, `claim_evidence_pointers`

Each claim evidence pointer stores:

- `artifact_id` (required)
- `section_ref` (optional section/offset reference identifier)
- `char_start` / `char_end` (optional explicit offsets, validated as a pair)
- `excerpt` (required source snippet)

This structure keeps evidence queryable by claim and artifact while retaining explicit claim-level provenance pointers.
