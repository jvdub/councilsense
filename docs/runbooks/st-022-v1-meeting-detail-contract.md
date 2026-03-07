# ST-022 Meeting Detail v1 Contract Specification and Approval Fixtures

- Story: ST-022
- Task: TASK-ST-022-01
- Contract version: `st-022-meeting-detail-v1`
- Fixture package version: `st022-v1-contract-approval-fixtures-v1`

Updated by TASK-ST-027-01 to define flag-state exposure semantics for additive reader blocks.

## Purpose

Freeze the additive v1 meeting detail contract shapes for:

- `planned`
- `outcomes`
- `planned_outcome_mismatches`
- `evidence_references_v2`

This contract is additive-only and does not remove, rename, or repurpose existing ST-006/ST-018 meeting detail fields.

## Top-level presence semantics

- `planned`: optional top-level object; omitted when additive reader blocks are disabled or unavailable.
- `outcomes`: optional top-level object; omitted when additive reader blocks are disabled or unavailable.
- `planned_outcome_mismatches`: optional top-level object; omitted when mismatch evaluation is disabled or unavailable.
- `evidence_references_v2`: additive evidence shape used within v1 additive blocks.

When a block is present, all fields marked "required" below are required.

Flag-state rules:

- Flag off: baseline ST-006/ST-018/ST-026 meeting detail semantics remain unchanged; `planned`, `outcomes`, and `planned_outcome_mismatches` are omitted.
- Flag on: additive blocks may be serialized without changing any baseline field names, types, or value semantics.
- Disabled or unavailable additive blocks must be omitted, never serialized as `null`.

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

Equal-precision ordering for serialized evidence references uses this deterministic tie-break chain:

- `document_kind` ascending
- `artifact_id` ascending
- `section_path` when present, otherwise `section_ref`, ascending
- `char_start` ascending when present
- `char_end` ascending when present
- normalized excerpt text ascending

This ordering is comparator-based and remains stable across reruns for identical source inputs.

Item-level presence semantics inside additive blocks:

- `evidence_references_v2` is optional on `planned.items[*]`, `outcomes.items[*]`, and `planned_outcome_mismatches.items[*]`.
- Omit `evidence_references_v2` when v2 evidence projection is unavailable for that item.
- Serialize `evidence_references_v2: []` when v2 projection is available for that item but no grounded references qualify.
- Do not serialize `evidence_references_v2: null`.

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

`planned.items[*].evidence_references_v2` is optional and follows the item-level presence semantics above.

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

`outcomes.items[*].evidence_references_v2` is optional and follows the item-level presence semantics above.

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

`planned_outcome_mismatches.items[*].evidence_references_v2` is optional and follows the item-level presence semantics above.

`outcome_id` may be `null` for unmatched planned items.

## ST-027 additive exposure matrix

| Scenario                         | `planned`                         | `outcomes`                        | `planned_outcome_mismatches`            | Item `evidence_references_v2` behavior                              |
| -------------------------------- | --------------------------------- | --------------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| Flag off baseline                | omitted                           | omitted                           | omitted                                 | n/a                                                                 |
| Flag on, evidence v2 available   | present when additive data exists | present when additive data exists | present when mismatch evaluation exists | include array; use `[]` when evaluated but no qualifying references |
| Flag on, evidence v2 unavailable | present when additive data exists | present when additive data exists | present when mismatch evaluation exists | omit field on affected items; never serialize `null`                |

## Contract examples

Flag off baseline-compatible response fragment:

```json
{
  "id": "meeting-st027-flag-off",
  "city_id": "city-eagle-mountain-ut",
  "meeting_uid": "uid-st027-flag-off",
  "title": "Regular City Council Meeting",
  "status": "processed",
  "confidence_label": "high",
  "reader_low_confidence": false,
  "publication_id": "pub-st027-flag-off",
  "published_at": "2026-03-07T14:30:00Z",
  "summary": "Council approved the consent agenda and deferred one procurement item.",
  "key_decisions": ["Approved consent agenda"],
  "key_actions": ["Staff to revise the procurement contract"],
  "notable_topics": ["Consent agenda", "Procurement"],
  "claims": [],
  "evidence_references": [],
  "evidence_references_v2": []
}
```

Flag on with additive blocks and available evidence v2:

```json
{
  "id": "meeting-st027-flag-on-available",
  "planned": {
    "generated_at": "2026-03-07T14:00:00Z",
    "source_coverage": {
      "minutes": "present",
      "agenda": "present",
      "packet": "present"
    },
    "items": [
      {
        "planned_id": "planned-100",
        "title": "Procurement contract approval",
        "category": "procurement",
        "status": "planned",
        "confidence": "high",
        "evidence_references_v2": []
      }
    ]
  },
  "outcomes": {
    "generated_at": "2026-03-07T14:20:00Z",
    "authority_source": "minutes",
    "items": [
      {
        "outcome_id": "outcome-100",
        "title": "Procurement contract deferred",
        "result": "deferred",
        "confidence": "high",
        "evidence_references_v2": []
      }
    ]
  },
  "planned_outcome_mismatches": {
    "summary": {
      "total": 1,
      "high": 1,
      "medium": 0,
      "low": 0
    },
    "items": [
      {
        "mismatch_id": "mismatch-100",
        "planned_id": "planned-100",
        "outcome_id": "outcome-100",
        "severity": "high",
        "mismatch_type": "disposition_change",
        "description": "Agenda planned approval but recorded outcome is deferment.",
        "reason_codes": ["outcome_changed"],
        "evidence_references_v2": []
      }
    ]
  }
}
```

Flag on with additive blocks and unavailable evidence v2:

```json
{
  "id": "meeting-st027-flag-on-unavailable",
  "planned": {
    "generated_at": "2026-03-07T15:00:00Z",
    "source_coverage": {
      "minutes": "missing",
      "agenda": "present",
      "packet": "present"
    },
    "items": [
      {
        "planned_id": "planned-200",
        "title": "Utility rate adjustment resolution",
        "category": "ordinance",
        "status": "planned",
        "confidence": "medium"
      }
    ]
  },
  "outcomes": {
    "generated_at": "2026-03-07T15:10:00Z",
    "authority_source": "minutes",
    "items": [
      {
        "outcome_id": "outcome-200",
        "title": "Outcome unavailable pending minutes",
        "result": "unresolved",
        "confidence": "low"
      }
    ]
  },
  "planned_outcome_mismatches": {
    "summary": {
      "total": 1,
      "high": 0,
      "medium": 1,
      "low": 0
    },
    "items": [
      {
        "mismatch_id": "mismatch-200",
        "planned_id": "planned-200",
        "outcome_id": null,
        "severity": "medium",
        "mismatch_type": "authority_missing",
        "description": "Minutes are unavailable, so the final outcome cannot yet be compared against the planned item.",
        "reason_codes": ["missing_authoritative_minutes"]
      }
    ]
  }
}
```

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

ST-027 exposure examples:

- Backend: `backend/tests/fixtures/st027_reader_api_additive_contract_examples.json`
- Covers flag-off baseline parity, flag-on additive presence, and safe omission when `evidence_references_v2` is unavailable.

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
