# ST-034 Meeting Detail Resident Scan Contract

- Story: ST-034
- Task: TASK-ST-034-01
- Scope: frontend-only resident-scan flag semantics, render-mode resolution, and scan-card component contract

## Frontend flag contract

- `NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED`
  - `false` by default
  - hard-disables resident scan cards and preserves baseline meeting detail rendering
  - only enables resident scan mode when top-level `structured_relevance` is present and valid

## Deterministic precedence

1. If `NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED` is not `true`, render `baseline`.
2. If top-level `structured_relevance` is missing, render `baseline`.
3. If top-level `structured_relevance` is present but has no valid `subject`, `location`, `action`, `scale`, or `impact_tags` members, render `baseline`.
4. Otherwise render `resident_scan`.
5. Inside `resident_scan` mode, prefer `outcomes.items[*]` cards when item-level resident-relevance fields are valid.
6. If no outcome-backed cards are valid, fall back to `planned.items[*]` cards.
7. If item-level resident-relevance fields are missing or malformed, keep `resident_scan` mode and fall back to a single meeting-summary card from top-level `structured_relevance`.

## Component model

- Card sources:
  - `outcome` for item-level outcome cards
  - `planned` for item-level planned cards when no outcome cards are available
  - `meeting` for top-level summary fallback when item-level data is absent or partial
- Core fields:
  - `subject` labeled as `What`
  - `location` labeled as `Where`
  - `action` labeled as `Action`
  - `scale` labeled as `Scale`
- Field semantics:
  - each field exposes `state`, `value`, `confidence`, and `evidenceReferences`
  - missing subfields stay explicit as `state = missing`; they do not force baseline fallback
- Impact tags:
  - optional
  - supported tags are `housing`, `traffic`, `utilities`, `parks`, `fees`, and `land_use`
  - ordering stays deterministic: `housing`, `traffic`, `utilities`, `parks`, `fees`, `land_use`
- Card state:
  - `complete` when all four core fields are present
  - `partial` when one or more core fields are missing

## Scenario matrix

| Resident scan flag | `structured_relevance` | Item-level resident relevance         | Resolved mode   | Card contract | Result                               |
| ------------------ | ---------------------- | ------------------------------------- | --------------- | ------------- | ------------------------------------ |
| off                | any                    | any                                   | `baseline`      | `missing`     | baseline-only detail                 |
| on                 | missing                | any                                   | `baseline`      | `missing`     | baseline-only detail                 |
| on                 | invalid                | any                                   | `baseline`      | `missing`     | baseline-only detail                 |
| on                 | valid                  | valid outcome items                   | `resident_scan` | `present`     | outcome-backed cards                 |
| on                 | valid                  | no outcome cards, valid planned items | `resident_scan` | `present`     | planned-backed cards                 |
| on                 | valid                  | missing or malformed item fields      | `resident_scan` | `partial`     | single meeting-summary fallback card |

## Fallback notes

- Baseline detail remains unchanged whenever the resident-scan flag is off.
- Baseline detail remains unchanged whenever top-level `structured_relevance` is missing.
- Partial or malformed item-level resident-relevance fields do not block resident scan mode once the top-level contract is valid.
- Unsupported impact tags and malformed resident-relevance members are ignored at field level rather than rendered as placeholders.

## Integration notes

- TASK-ST-034-02 should consume the resident-scan resolver and card models rather than re-deriving payload validity in the route component.
- TASK-ST-034-03 should attach navigation affordances only after card source and field state are resolved.
