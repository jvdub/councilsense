# Additive Reader API Contract for Resident-Relevance Fields

**Task ID:** TASK-ST-033-01  
**Story:** ST-033  
**Bucket:** backend  
**Requirement Links:** ST-033 Acceptance Criteria #1, #2, and #3, FR-4, REQUIREMENTS §12.3 Web App

## Objective

Define the additive reader API contract for resident-relevance fields in meeting detail responses and additive item blocks, including safe-omit behavior.

## Scope

- Define field semantics for `subject`, `location`, `action`, `scale`, and `impact_tags` at meeting-level and item-level where applicable.
- Define omission rules for unavailable structured relevance values.
- Specify compatibility behavior for flag-off and legacy publication scenarios.
- Out of scope: serializer implementation and performance checks.

## Inputs / Dependencies

- ST-027 additive reader API contract patterns.
- TASK-ST-032-01 structured relevance model.

## Implementation Notes

- Keep all new fields optional and non-breaking.
- Prefer explicit schema examples for present, partial, and omitted structured values.
- Align with existing evidence v2 additive semantics when linking supporting evidence.

## Acceptance Criteria

1. Additive meeting detail contract is documented for resident-relevance fields.
2. Item-level inclusion rules are explicit for planned/outcomes blocks when structured relevance is available.
3. Omission behavior is defined for unsupported or backfill-incomplete cases.
4. Contract examples preserve baseline compatibility for clients that ignore the new fields.

## Validation

- Review schema examples against current meeting detail payloads.
- Verify omission rules do not require null placeholders.
- Confirm compatibility with additive field patterns established in ST-027.

## Deliverables

- Additive contract specification for resident-relevance fields.
- Presence/omission matrix for meeting-level and item-level payloads.
- Example payloads for nominal and sparse cases.

## Contract Shape

### Meeting-Level Additive Block

- Meeting detail responses may include an optional top-level `structured_relevance` object.
- `structured_relevance` is additive-only and does not replace or rename any existing meeting detail fields.
- `structured_relevance` is omitted entirely when no meeting-level resident-relevance values are available, when the resident-relevance feature is disabled, or when legacy/backfill data does not contain supported structured values.

### Meeting-Level Field Semantics

- `structured_relevance.subject`: concise identifier for the project, ordinance, plan, contract, corridor, district, parcel, or comparable resident-facing subject.
- `structured_relevance.location`: place anchor for where the item applies, such as a street, district, neighborhood, parcel area, or facility.
- `structured_relevance.action`: disposition or status phrase supported by the source bundle, such as `approved`, `deferred`, or `unresolved`.
- `structured_relevance.scale`: material magnitude phrase such as units, acres, dollars, dates, or vote counts when explicitly grounded.
- `structured_relevance.impact_tags`: deterministic list of resident-facing impact categories.

### Item-Level Additive Fields

- Planned and outcome items may include additive resident-relevance fields directly on each item object.
- Supported item-level fields are `subject`, `location`, `action`, `scale`, and `impact_tags`.
- Item-level resident-relevance fields are allowed on `planned.items[*]` and `outcomes.items[*]`.
- `planned_outcome_mismatches.items[*]` remain unchanged for this contract and do not add resident-relevance fields.
- Item-level resident-relevance fields are omitted when the matching structured item data is unavailable, unsupported, or not mapped for that item.

### Field Object Shape

- `subject`, `location`, `action`, and `scale` use the same additive object shape:

```json
{
  "value": "North Gateway rezoning application",
  "confidence": "high",
  "evidence_references_v2": [
    {
      "evidence_id": "ev2-st033-subject-100",
      "document_id": "doc-minutes-100",
      "document_kind": "minutes",
      "artifact_id": "artifact-minutes-100",
      "section_path": "minutes.section.4",
      "page_start": 6,
      "page_end": 6,
      "char_start": 88,
      "char_end": 176,
      "precision": "offset",
      "confidence": "high",
      "excerpt": "Council approved the North Gateway rezoning application covering 142 acres and 893 units."
    }
  ]
}
```

- `value` is required when the field object is present.
- `confidence` is optional and, when present, must follow the additive structured-confidence vocabulary already used internally: `high`, `medium`, or `low`.
- `evidence_references_v2` is optional and reuses the additive evidence-v2 schema and ordering conventions already established for reader payloads.

### Impact Tag Shape

- `impact_tags` is an optional array.
- Each tag entry uses the following additive shape:

```json
{
  "tag": "housing",
  "confidence": "high",
  "evidence_references_v2": [
    {
      "evidence_id": "ev2-st033-impact-100",
      "document_id": "doc-minutes-100",
      "document_kind": "minutes",
      "artifact_id": "artifact-minutes-100",
      "section_path": "minutes.section.4",
      "page_start": 6,
      "page_end": 6,
      "char_start": 88,
      "char_end": 176,
      "precision": "offset",
      "confidence": "high",
      "excerpt": "Council approved the North Gateway rezoning application covering 142 acres and 893 units."
    }
  ]
}
```

- `tag` is required when the impact-tag object is present.
- `confidence` is optional.
- `evidence_references_v2` is optional.
- When multiple tags are present, ordering should remain deterministic and follow the approved resident-impact ordering used by structured extraction: `housing`, `traffic`, `utilities`, `parks`, `fees`, `land_use`.

## Omission Rules

- Omit `structured_relevance` entirely when there are no meeting-level resident-relevance fields to expose.
- Omit any unavailable `subject`, `location`, `action`, `scale`, or `impact_tags` members rather than emitting `null`.
- Omit `evidence_references_v2` when supporting evidence cannot be projected in additive evidence-v2 form; do not emit `null` placeholders.
- Omit resident-relevance fields for legacy publications and backfill-incomplete records that do not contain supported structured values.
- Omit all resident-relevance fields when the resident-relevance feature is disabled, even if ST-027 additive planned/outcomes blocks remain enabled.
- Omit item-level resident-relevance fields for individual planned or outcome items that do not have a matching structured item payload, even if meeting-level `structured_relevance` is present.

## Presence Matrix

| Scenario                                           | Top-level `structured_relevance` | `planned.items[*]` relevance fields | `outcomes.items[*]` relevance fields | `planned_outcome_mismatches.items[*]` relevance fields |
| -------------------------------------------------- | -------------------------------- | ----------------------------------- | ------------------------------------ | ------------------------------------------------------ |
| Resident-relevance flag off                        | omitted                          | omitted                             | omitted                              | omitted                                                |
| Flag on, structured relevance available            | optional, per field              | optional, per item field            | optional, per item field             | omitted                                                |
| Flag on, sparse structured relevance               | optional partial object          | optional partial fields only        | optional partial fields only         | omitted                                                |
| Flag on, legacy or backfill-incomplete publication | omitted                          | omitted                             | omitted                              | omitted                                                |

## Example Payloads

### Nominal Additive Example

```json
{
  "id": "meeting-st033-full",
  "structured_relevance": {
    "subject": {
      "value": "North Gateway rezoning application",
      "confidence": "high",
      "evidence_references_v2": [
        {
          "evidence_id": "ev2-st033-subject-100",
          "document_id": "doc-minutes-100",
          "document_kind": "minutes",
          "artifact_id": "artifact-minutes-100",
          "section_path": "minutes.section.4",
          "page_start": 6,
          "page_end": 6,
          "char_start": 88,
          "char_end": 176,
          "precision": "offset",
          "confidence": "high",
          "excerpt": "Council approved the North Gateway rezoning application covering 142 acres and 893 units."
        }
      ]
    },
    "location": {
      "value": "North Gateway District",
      "confidence": "high"
    },
    "action": {
      "value": "approved",
      "confidence": "high"
    },
    "scale": {
      "value": "142 acres and 893 units",
      "confidence": "high"
    },
    "impact_tags": [
      {
        "tag": "housing",
        "confidence": "high"
      },
      {
        "tag": "land_use",
        "confidence": "high"
      }
    ]
  },
  "planned": {
    "items": [
      {
        "planned_id": "planned-100",
        "subject": {
          "value": "North Gateway rezoning application",
          "confidence": "high"
        },
        "location": {
          "value": "North Gateway District",
          "confidence": "high"
        },
        "scale": {
          "value": "142 acres and 893 units",
          "confidence": "high"
        },
        "impact_tags": [
          {
            "tag": "housing",
            "confidence": "high"
          },
          {
            "tag": "land_use",
            "confidence": "high"
          }
        ]
      }
    ]
  },
  "outcomes": {
    "items": [
      {
        "outcome_id": "outcome-100",
        "subject": {
          "value": "North Gateway rezoning application",
          "confidence": "high"
        },
        "location": {
          "value": "North Gateway District",
          "confidence": "high"
        },
        "action": {
          "value": "approved",
          "confidence": "high"
        },
        "scale": {
          "value": "142 acres and 893 units",
          "confidence": "high"
        },
        "impact_tags": [
          {
            "tag": "housing",
            "confidence": "high"
          },
          {
            "tag": "land_use",
            "confidence": "high"
          }
        ]
      }
    ]
  }
}
```

### Sparse Additive Example

```json
{
  "id": "meeting-st033-sparse",
  "structured_relevance": {
    "subject": {
      "value": "Main Street paving contract",
      "confidence": "medium"
    },
    "location": {
      "value": "Main Street",
      "confidence": "medium"
    },
    "impact_tags": [
      {
        "tag": "traffic",
        "confidence": "medium"
      }
    ]
  },
  "planned": {
    "items": [
      {
        "planned_id": "planned-200",
        "subject": {
          "value": "Main Street paving contract",
          "confidence": "medium"
        }
      }
    ]
  },
  "outcomes": {
    "items": [
      {
        "outcome_id": "outcome-200",
        "action": {
          "value": "unresolved",
          "confidence": "low"
        }
      }
    ]
  }
}
```
