import { describe, expect, it } from "vitest";

import type { MeetingDetailResponse } from "../models/meetings";
import {
  MEETING_DETAIL_MISMATCH_SIGNALS_FLAG,
  MEETING_DETAIL_PLANNED_OUTCOMES_FLAG,
  getMeetingDetailFeatureFlags,
  resolveMeetingDetailRenderState,
} from "./detailRenderMode";

function buildMeetingDetail(
  overrides: Partial<MeetingDetailResponse> = {},
): MeetingDetailResponse {
  return {
    id: "meeting-1",
    city_id: "city-1",
    meeting_uid: "uid-1",
    title: "Meeting 1",
    created_at: "2026-03-07T14:00:00Z",
    updated_at: "2026-03-07T14:10:00Z",
    status: "processed",
    confidence_label: "high",
    reader_low_confidence: false,
    publication_id: "publication-1",
    published_at: "2026-03-07T14:15:00Z",
    summary: "Summary",
    key_decisions: ["Decision"],
    key_actions: ["Action"],
    notable_topics: ["Topic"],
    claims: [],
    planned: {
      generated_at: "2026-03-07T14:00:00Z",
      source_coverage: {
        minutes: "present",
        agenda: "present",
        packet: "present",
      },
      items: [
        {
          planned_id: "planned-1",
          title: "Planned item",
          category: "ordinance",
          status: "planned",
          confidence: "high",
          evidence_references_v2: [],
        },
      ],
    },
    outcomes: {
      generated_at: "2026-03-07T14:05:00Z",
      authority_source: "minutes",
      items: [
        {
          outcome_id: "outcome-1",
          title: "Outcome item",
          result: "approved",
          confidence: "high",
          evidence_references_v2: [],
        },
      ],
    },
    planned_outcome_mismatches: {
      summary: {
        total: 1,
        high: 1,
        medium: 0,
        low: 0,
      },
      items: [
        {
          mismatch_id: "mismatch-1",
          planned_id: "planned-1",
          outcome_id: "outcome-1",
          severity: "high",
          mismatch_type: "disposition_change",
          description: "Changed outcome",
          reason_codes: ["outcome_changed"],
          evidence_references_v2: [],
        },
      ],
    },
    ...overrides,
  };
}

describe("meeting detail render mode resolution", () => {
  it("hard-disables additive mode when the planned/outcomes flag is off", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "false",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "true",
    });

    const result = resolveMeetingDetailRenderState(buildMeetingDetail(), flags);

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "planned_outcomes_flag_disabled",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "mismatch_flag_disabled",
      flags: {
        plannedOutcomesEnabled: false,
        mismatchSignalsEnabled: false,
      },
    });
  });

  it("activates additive mode when the flag is on and planned/outcomes blocks are valid", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "true",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "false",
    });

    const result = resolveMeetingDetailRenderState(buildMeetingDetail(), flags);

    expect(result).toMatchObject({
      mode: "additive",
      modeFallbackReason: null,
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "mismatch_flag_disabled",
      contract: {
        planned: "present",
        outcomes: "present",
        mismatches: "present",
      },
    });
  });

  it("falls back to baseline when required additive blocks are missing", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "true",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "true",
    });

    const result = resolveMeetingDetailRenderState(
      buildMeetingDetail({ outcomes: undefined }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "missing_outcomes_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      contract: {
        planned: "present",
        outcomes: "missing",
        mismatches: "present",
      },
    });
  });

  it("falls back to baseline when required additive blocks are partial or malformed", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "true",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "true",
    });

    const result = resolveMeetingDetailRenderState(
      buildMeetingDetail({
        planned: {
          generated_at: "2026-03-07T14:00:00Z",
          source_coverage: {
            minutes: "present",
            agenda: "present",
            packet: "present",
          },
          items: [
            {
              planned_id: "planned-1",
              title: "Incomplete planned item",
              category: "ordinance",
              status: "planned",
              confidence: "unknown" as "high",
              evidence_references_v2: [],
            },
          ],
        },
      }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "baseline",
      modeFallbackReason: "invalid_planned_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      contract: {
        planned: "invalid",
        outcomes: "present",
        mismatches: "present",
      },
    });
  });

  it("enables mismatch signals only when additive mode is active and the mismatch block is valid", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "true",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "true",
    });

    const result = resolveMeetingDetailRenderState(buildMeetingDetail(), flags);

    expect(result).toMatchObject({
      mode: "additive",
      mismatchSignalsEnabled: true,
      mismatchFallbackReason: null,
      contract: {
        mismatches: "present",
      },
    });
  });

  it("keeps additive mode but disables mismatch signals when mismatch data is absent", () => {
    const flags = getMeetingDetailFeatureFlags({
      [MEETING_DETAIL_PLANNED_OUTCOMES_FLAG]: "true",
      [MEETING_DETAIL_MISMATCH_SIGNALS_FLAG]: "true",
    });

    const result = resolveMeetingDetailRenderState(
      buildMeetingDetail({ planned_outcome_mismatches: undefined }),
      flags,
    );

    expect(result).toMatchObject({
      mode: "additive",
      modeFallbackReason: null,
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "missing_mismatch_block",
      contract: {
        planned: "present",
        outcomes: "present",
        mismatches: "missing",
      },
    });
  });
});