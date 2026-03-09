import { describe, expect, it } from "vitest";

import type { MeetingDetailResponse } from "../models/meetings";
import {
  MEETING_DETAIL_RESIDENT_SCAN_FLAG,
  getMeetingResidentScanFeatureFlags,
  resolveMeetingResidentScanRenderState,
} from "./residentScanMode";

function buildMeetingDetail(
  overrides: Partial<MeetingDetailResponse> = {},
): MeetingDetailResponse {
  return {
    id: "meeting-1",
    city_id: "city-1",
    city_name: "City 1",
    meeting_uid: "uid-1",
    title: "Meeting 1",
    created_at: "2026-03-09T14:00:00Z",
    updated_at: "2026-03-09T14:10:00Z",
    meeting_date: "2026-03-09",
    body_name: "City Council",
    source_document_kind: "minutes",
    source_document_url: "https://example.org/minutes/meeting-1.pdf",
    status: "processed",
    confidence_label: "high",
    reader_low_confidence: false,
    publication_id: "publication-1",
    published_at: "2026-03-09T14:15:00Z",
    summary: "Summary",
    key_decisions: ["Decision"],
    key_actions: ["Action"],
    notable_topics: ["Topic"],
    claims: [],
    structured_relevance: {
      subject: {
        value: "North Gateway rezoning application",
        confidence: "high",
      },
      location: {
        value: "North Gateway District",
        confidence: "high",
      },
      action: {
        value: "approved",
        confidence: "high",
      },
      scale: {
        value: "142 acres and 893 units",
        confidence: "high",
      },
      impact_tags: [
        {
          tag: "housing",
          confidence: "high",
        },
        {
          tag: "land_use",
          confidence: "high",
        },
      ],
    },
    planned: {
      generated_at: "2026-03-09T14:00:00Z",
      source_coverage: {
        minutes: "present",
        agenda: "present",
        packet: "present",
      },
      items: [
        {
          planned_id: "planned-1",
          title: "North Gateway rezoning application",
          category: "ordinance",
          status: "planned",
          confidence: "high",
          evidence_references_v2: [],
          subject: {
            value: "North Gateway rezoning application",
            confidence: "high",
          },
          location: {
            value: "North Gateway District",
            confidence: "high",
          },
          scale: {
            value: "142 acres and 893 units",
            confidence: "high",
          },
        },
      ],
    },
    outcomes: {
      generated_at: "2026-03-09T14:05:00Z",
      authority_source: "minutes",
      items: [
        {
          outcome_id: "outcome-1",
          title: "North Gateway rezoning approved",
          result: "approved",
          confidence: "high",
          evidence_references_v2: [],
          subject: {
            value: "North Gateway rezoning application",
            confidence: "high",
          },
          location: {
            value: "North Gateway District",
            confidence: "high",
          },
          action: {
            value: "approved",
            confidence: "high",
          },
          scale: {
            value: "142 acres and 893 units",
            confidence: "high",
          },
          impact_tags: [
            {
              tag: "housing",
              confidence: "high",
            },
            {
              tag: "land_use",
              confidence: "high",
            },
          ],
        },
      ],
    },
    planned_outcome_mismatches: {
      summary: {
        total: 0,
        high: 0,
        medium: 0,
        low: 0,
      },
      items: [],
    },
    ...overrides,
  };
}

describe("meeting resident scan render mode resolution", () => {
  it("hard-disables resident scan mode when the frontend flag is off", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "false",
    });

    const result = resolveMeetingResidentScanRenderState(buildMeetingDetail(), flags);

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "resident_scan_flag_disabled",
      contract: {
        structuredRelevance: "present",
        cards: "missing",
      },
      cards: [],
    });
  });

  it("preserves baseline mode when top-level structured relevance is missing", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "true",
    });

    const result = resolveMeetingResidentScanRenderState(
      buildMeetingDetail({ structured_relevance: undefined }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "missing_structured_relevance",
      contract: {
        structuredRelevance: "missing",
        cards: "missing",
      },
      cards: [],
    });
  });

  it("falls back to baseline when the top-level structured relevance block is malformed", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "true",
    });

    const result = resolveMeetingResidentScanRenderState(
      buildMeetingDetail({
        structured_relevance: {
          subject: {
            confidence: "high",
          },
        } as unknown as MeetingDetailResponse["structured_relevance"],
      }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "invalid_structured_relevance",
      contract: {
        structuredRelevance: "invalid",
        cards: "missing",
      },
      cards: [],
    });
  });

  it("resolves resident scan mode and prefers outcome-backed cards when additive data is valid", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "true",
    });

    const result = resolveMeetingResidentScanRenderState(buildMeetingDetail(), flags);

    expect(result).toMatchObject({
      mode: "resident_scan",
      modeFallbackReason: null,
      contract: {
        structuredRelevance: "present",
        cards: "present",
      },
    });
    expect(result.cards).toHaveLength(1);
    expect(result.cards[0]).toMatchObject({
      id: "outcome:outcome-1",
      source: "outcome",
      sourceItemId: "outcome-1",
      title: "North Gateway rezoning application",
      state: "complete",
      impactTags: [
        { tag: "housing", confidence: "high" },
        { tag: "land_use", confidence: "high" },
      ],
    });
    expect(result.cards[0].fields.subject).toMatchObject({
      label: "What",
      value: "North Gateway rezoning application",
      state: "present",
    });
  });

  it("keeps resident scan mode and emits a partial summary card when item-level fields are unavailable", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "true",
    });

    const result = resolveMeetingResidentScanRenderState(
      buildMeetingDetail({
        planned: {
          generated_at: "2026-03-09T14:00:00Z",
          source_coverage: {
            minutes: "present",
            agenda: "present",
            packet: "present",
          },
          items: [],
        },
        outcomes: {
          generated_at: "2026-03-09T14:05:00Z",
          authority_source: "minutes",
          items: [],
        },
        structured_relevance: {
          subject: {
            value: "Main Street paving contract",
            confidence: "medium",
          },
          impact_tags: [
            {
              tag: "traffic",
              confidence: "medium",
            },
          ],
        },
      }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "resident_scan",
      modeFallbackReason: null,
      contract: {
        structuredRelevance: "present",
        cards: "partial",
      },
    });
    expect(result.cards).toHaveLength(1);
    expect(result.cards[0]).toMatchObject({
      id: "meeting:summary",
      source: "meeting",
      state: "partial",
      title: "Main Street paving contract",
      impactTags: [{ tag: "traffic", confidence: "medium" }],
    });
    expect(result.cards[0].fields.location.state).toBe("missing");
    expect(result.cards[0].fields.action.state).toBe("missing");
    expect(result.cards[0].fields.scale.state).toBe("missing");
  });

  it("ignores malformed item-level relevance members while keeping valid partial item cards", () => {
    const flags = getMeetingResidentScanFeatureFlags({
      [MEETING_DETAIL_RESIDENT_SCAN_FLAG]: "true",
    });

    const result = resolveMeetingResidentScanRenderState(
      buildMeetingDetail({
        outcomes: {
          generated_at: "2026-03-09T14:05:00Z",
          authority_source: "minutes",
          items: [
            {
              outcome_id: "outcome-1",
              title: "Malformed resident-scan outcome",
              result: "approved",
              confidence: "high",
              evidence_references_v2: [],
              subject: {
                confidence: "high",
              } as unknown as NonNullable<
                NonNullable<MeetingDetailResponse["outcomes"]>["items"][number]["subject"]
              >,
            },
          ],
        },
      }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "resident_scan",
      contract: {
        structuredRelevance: "present",
        cards: "partial",
      },
    });
    expect(result.cards).toHaveLength(1);
    expect(result.cards[0]).toMatchObject({
      id: "planned:planned-1",
      source: "planned",
      state: "partial",
    });
    expect(result.cards[0].fields.action.state).toBe("missing");
  });
});