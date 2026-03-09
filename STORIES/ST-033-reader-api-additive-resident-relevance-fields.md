# Resident Relevance: Reader API Additive Subject, Location, and Impact Fields

**Story ID:** ST-033  
**Phase:** Phase 4 (Resident relevance + explainability)  
**Requirement Links:** FR-4, FR-6, §12.2 Summarization & Relevance Service, §12.3 Web App, §13.1 Resident Outcome, §13.5 Clarity Outcome, §14(3,10)

## User Story
As a frontend client, I want additive resident-relevance fields in meeting detail responses so I can present what an item is, where it applies, and why it may matter without breaking existing readers.

## Scope
- Add optional resident-relevance fields to meeting detail responses and additive planned/outcomes blocks.
- Expose structured values derived from summarization for `subject`, `location`, `action`, `scale`, and `impact_tags`, along with evidence linkage to the supporting excerpts.
- Preserve existing meeting detail semantics and fallback behavior when resident-relevance fields are absent.
- Keep the contract additive and version-safe so current consumers remain compatible.

## Acceptance Criteria
1. Meeting detail responses can include an additive resident-relevance block without changing required baseline fields.
2. Planned and outcome items can include optional resident-relevance fields when grounded structured extraction is available.
3. Resident-relevance fields are omitted, not null-filled, when upstream structured extraction is unavailable or unsupported for a meeting item.
4. Contract tests cover presence, omission, and deterministic ordering of `impact_tags` and any linked evidence references.
5. Existing clients that ignore the additive fields continue to function without behavioral regression.

## Implementation Tasks
- [ ] Define response contract additions for meeting-level and item-level resident-relevance fields.
- [ ] Project structured relevance values from persisted summary outputs into the meeting detail route.
- [ ] Add contract fixtures for nominal, sparse, and missing-structured-data cases.
- [ ] Verify safe omission behavior for legacy publications and partial backfill states.
- [ ] Add backend tests for additive compatibility and deterministic serialization.

## Dependencies
- ST-027
- ST-032

## Definition of Done
- Meeting detail payloads can expose resident-relevance structure without breaking baseline readers.
- Presence and omission semantics are explicit, tested, and additive-only.
- Structured relevance values remain traceable to grounded summary evidence.