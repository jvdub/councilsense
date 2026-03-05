# ST-018 Meeting Detail evidence_references Contract Decision

- Story: ST-018
- Tasks covered: TASK-ST-018-01 and TASK-ST-018-02
- Contract version: st-018-evidence-references-v1

## Decision

`evidence_references` is an additive top-level field on `GET /v1/meetings/{meeting_id}`.

- Type: `array[string]`
- Presence semantics: always present in meeting detail response
- Evidence-present behavior: non-empty array when at least one evidence pointer exists across claims
- Evidence-sparse behavior: explicit empty array `[]` (never omitted)

This follows existing ST-006 list-field conventions where collection fields are present and empty when no values are available.

## Additive-only invariants

- No legacy field is renamed, removed, or repurposed.
- Existing field types and value semantics remain unchanged.
- Existing nested claim/evidence payload remains unchanged.
- Only approved additive field for this story is `evidence_references`.

## Serialization format

Each entry is a deterministic pointer string serialized as:

`{excerpt} | {artifact_id}#{section_ref_or_no-section}:{char_start_or_?}-{char_end_or_?}`

Rules:
- dedupe by full serialized pointer string
- sort ascending lexicographically for stable output
- if `section_ref` is null use `no-section`
- if `char_start` or `char_end` is null use `?`

## Contract examples

Evidence-present:

```json
{
  "id": "meeting-st018-present",
  "summary": "Council approved a stormwater utility adjustment.",
  "key_decisions": ["Approved stormwater utility adjustment"],
  "key_actions": ["Staff to publish ordinance redline"],
  "notable_topics": ["Stormwater", "Budget"],
  "evidence_references": [
    "Council voted 5-2 to approve the stormwater utility adjustment. | artifact-st018-minutes#minutes.section.5:210-280",
    "Public works staff committed to publish the ordinance redline by Friday. | artifact-st018-action#minutes.section.7:410-470"
  ],
  "claims": [
    {
      "id": "claim-st018-present-1",
      "evidence": [
        {
          "id": "ptr-st018-present-1",
          "artifact_id": "artifact-st018-minutes"
        }
      ]
    }
  ]
}
```

Evidence-sparse:

```json
{
  "id": "meeting-st018-sparse",
  "summary": "Summary published with limited confidence due to sparse citations.",
  "key_decisions": [],
  "key_actions": [],
  "notable_topics": ["Follow-up"],
  "evidence_references": [],
  "claims": [
    {
      "id": "claim-st018-sparse-1",
      "evidence": []
    }
  ]
}
```

## Traceability

- ST-018 AC#1: field included when evidence exists
- ST-018 AC#2: additive-only with legacy compatibility
- ST-018 AC#3: explicit sparse behavior (`[]`) defined and testable
- Downstream tests: `backend/tests/test_meeting_detail_api.py`, `backend/tests/test_st018_evidence_references_contract.py`
