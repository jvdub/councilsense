# ST-022 Meeting Detail v1 Contract Specification and Approval Fixtures

- Story: ST-022
- Task: TASK-ST-022-01
- Contract version: `st-022-meeting-detail-v1`
- Fixture package version: `st022-v1-contract-approval-fixtures-v1`

## Purpose

Freeze the additive v1 meeting detail contract shapes for:

- `planned`
- `outcomes`
- `planned_outcome_mismatches`
- `evidence_references_v2`

This contract is additive-only and does not remove, rename, or repurpose existing ST-006/ST-018 meeting detail fields.

## Top-level presence semantics

- `planned`: optional top-level object; omitted when v1 additive blocks are unavailable.
- `outcomes`: optional top-level object; omitted when v1 additive blocks are unavailable.
- `planned_outcome_mismatches`: optional top-level object; omitted when mismatch evaluation is unavailable.
- `evidence_references_v2`: additive evidence shape used within v1 additive blocks.

When a block is present, all fields marked "required" below are required.

## `evidence_references_v2` shape

Evidence references are arrays of objects with these semantics.

| Field           | Type                                        | Required | Nullability  | Notes                                                           |
| --------------- | ------------------------------------------- | -------- | ------------ | --------------------------------------------------------------- |
| `evidence_id`   | `string`                                    | yes      | not nullable | Stable per publication payload.                                 |
| `document_id`   | `string`                                    | yes      | not nullable | Canonical document identifier.                                  |
| `document_kind` | `"minutes" \| "agenda" \| "packet"`         | yes      | not nullable | Source-kind contract is frozen to these v1 values.              |
| `artifact_id`   | `string`                                    | yes      | not nullable | Underlying artifact identifier.                                 |
| `section_path`  | `string`                                    | yes      | not nullable | Deterministic section locator path.                             |
| `page_start`    | `integer`                                   | no       | nullable     | Optional page range start for document formats with pagination. |
| `page_end`      | `integer`                                   | no       | nullable     | Optional page range end.                                        |
| `char_start`    | `integer`                                   | no       | nullable     | Optional character-offset precision.                            |
| `char_end`      | `integer`                                   | no       | nullable     | Optional character-offset precision.                            |
| `precision`     | `"offset" \| "span" \| "section" \| "file"` | yes      | not nullable | Precision ladder contract.                                      |
| `confidence`    | `"high" \| "medium" \| "low"`               | yes      | not nullable | Evidence confidence for the specific locator.                   |
| `excerpt`       | `string`                                    | yes      | not nullable | Human-readable supporting excerpt.                              |

## `planned` block shape

```json
{
  "generated_at": "2026-03-04T09:30:00Z",
  "source_coverage": {
    "minutes": "missing",
    "agenda": "present",
    "packet": "present"
  },
  "items": [
    {
      "planned_id": "planned-001",
      "title": "Public hearing on downtown parking amendments",
      "category": "hearing",
      "status": "planned",
      "confidence": "high",
      "evidence_references_v2": []
    }
  ]
}
```

`planned` required fields:

- `generated_at`
- `source_coverage`
- `items`

`planned.items[*]` required fields:

- `planned_id`
- `title`
- `category`
- `status`
- `confidence`
- `evidence_references_v2`

## `outcomes` block shape

```json
{
  "generated_at": "2026-03-04T09:35:00Z",
  "authority_source": "minutes",
  "items": [
    {
      "outcome_id": "outcome-001",
      "title": "Downtown parking amendments approved with changes",
      "result": "approved_with_amendments",
      "confidence": "high",
      "evidence_references_v2": []
    }
  ]
}
```

`outcomes` required fields:

- `generated_at`
- `authority_source`
- `items`

`outcomes.items[*]` required fields:

- `outcome_id`
- `title`
- `result`
- `confidence`
- `evidence_references_v2`

## `planned_outcome_mismatches` block shape

```json
{
  "summary": {
    "total": 1,
    "high": 0,
    "medium": 1,
    "low": 0
  },
  "items": [
    {
      "mismatch_id": "mismatch-001",
      "planned_id": "planned-001",
      "outcome_id": "outcome-001",
      "severity": "medium",
      "mismatch_type": "scope_change",
      "description": "Outcome narrowed hearing scope to commercial zones only.",
      "reason_codes": ["textual_delta"],
      "evidence_references_v2": []
    }
  ]
}
```

`planned_outcome_mismatches` required fields:

- `summary`
- `items`

`planned_outcome_mismatches.summary` required fields:

- `total`
- `high`
- `medium`
- `low`

`planned_outcome_mismatches.items[*]` required fields:

- `mismatch_id`
- `planned_id`
- `outcome_id`
- `severity`
- `mismatch_type`
- `description`
- `reason_codes`
- `evidence_references_v2`

`outcome_id` may be `null` for unmatched planned items.

## Approval fixtures and sign-off

Fixture package location:

- Backend: `backend/tests/fixtures/st022_v1_contract_approval_fixtures.json`
- Frontend: `frontend/src/lib/api/fixtures/st022_v1_contract_approval_fixtures.json`

Fixture scenarios included:

1. Nominal multi-source publication (`processed`)
2. Partial-source publication (`processed`)
3. Limited-confidence publication (`limited_confidence`)

Approval status captured in fixture package metadata:

- `approval.status`: `approved`
- `approval.reviewers`: backend owner, frontend owner, product/platform owner

## Traceability

- ST-022 AC#1: versioned v1 contract + fixtures approved and checked in
- AGENDA_PLAN §4: v1-first additive payload strategy
- AGENDA_PLAN §5 Phase 0: contract freeze before implementation phases

## TASK-ST-022-03: Idempotency key naming and stage ownership contract

### Idempotency key naming rules (v1)

- Version prefix: `st022-idem-v1`
- Canonical format: `st022-idem-v1:<stage>:<k1>=<v1>:<k2>=<v2>:...`
- Stages frozen for this contract: `ingest`, `extract`, `summarize`, `publish`
- All values are normalized as non-empty trimmed strings and URL-encoded (`-_.~` safe set) before concatenation.
- Ordering is deterministic and stage-specific; no caller-specific field reordering is allowed.

Stage field order and key composition:

| Stage       | Canonical ordered fields                                      |
| ----------- | ------------------------------------------------------------- |
| `ingest`    | `city`, `meeting`, `source`, `revision`, `checksum`           |
| `extract`   | `city`, `meeting`, `source`, `revision`, `checksum`           |
| `summarize` | `city`, `meeting`, `bundle_revision`, `coverage_checksum`     |
| `publish`   | `city`, `meeting`, `publication_revision`, `summary_checksum` |

Examples:

- Normal ingest: `st022-idem-v1:ingest:city=city-seattle-wa:meeting=meeting-2026-03-04-regular:source=minutes:revision=rev-2026-03-04T09%3A30%3A00Z:checksum=sha256%3A111aaa`
- Rerun with same summarize inputs (same key): `st022-idem-v1:summarize:city=city-seattle-wa:meeting=meeting-2026-03-04-regular:bundle_revision=bundle-v1:coverage_checksum=sha256%3Acoverage-aaa`
- Duplicate payload with changed summarize revision (different key): `st022-idem-v1:summarize:city=city-seattle-wa:meeting=meeting-2026-03-04-regular:bundle_revision=bundle-v2:coverage_checksum=sha256%3Acoverage-aaa`

Duplicate/replay expectations:

- Same stage + same canonical field values MUST produce the exact same idempotency key.
- Same stage + any changed canonical field value MUST produce a different idempotency key.
- Downstream dedupe and persistence constraints consume these keys to enforce no-duplicate stage outcomes.

Executable reference: `backend/src/councilsense/app/st022_stage_contracts.py`

### Stage ownership and handoff boundaries (v1)

| Stage       | Producer                        | Consumer                  | Persisted handoff state                                                           | Boundary                                                                                           |
| ----------- | ------------------------------- | ------------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `ingest`    | bundle planner + source adapter | extract stage worker      | raw artifact persisted and extract queue payload recorded                         | ingest owns external source retrieval and canonical raw artifact write; extract owns parsing       |
| `extract`   | extract stage worker            | summarize stage worker    | normalized extracted text artifact persisted and summarize queue payload recorded | extract owns parser selection and normalized extraction output; summarize owns synthesis           |
| `summarize` | summarize stage worker          | publish stage worker      | summary payload persisted and publish queue payload recorded                      | summarize owns claim synthesis and evidence packaging; publish owns publication state transition   |
| `publish`   | publish stage worker            | meeting detail reader API | publication record committed with final status and source coverage diagnostics    | publish owns durable meeting publication write; reader API owns projection and response formatting |

Ownership invariants:

- Each stage has exactly one producer and one primary consumer in the v1 flow.
- Handoff state is durable before the consumer stage starts.
- Stage boundaries are additive and do not alter existing notification/governance idempotency contracts.

Executable reference: `backend/src/councilsense/app/st022_stage_contracts.py#ST022_STAGE_OWNERSHIP_TABLE`
