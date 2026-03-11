import { describe, expect, it } from "vitest";

import {
  MEETING_EXPLORER_FLAG,
  buildMeetingDetailHref,
  canRequestMeetingSummary,
  getMeetingTileActionLabel,
  getMeetingTileBadgeLabel,
  getMeetingTileStatusCopy,
  isMeetingExplorerEnabled,
  resolveMeetingReturnPath,
} from "./explorer";
import { type MeetingListItem } from "../models/meetings";

function buildMeeting(
  processingStatus: MeetingListItem["processing"]["processing_status"],
  meetingDate = "2026-03-09",
): MeetingListItem {
  return {
    id: `meeting-${processingStatus}`,
    meeting_id: processingStatus === "processed" ? "meeting-detail-1" : null,
    city_id: "seattle-wa",
    city_name: "Seattle",
    meeting_uid: null,
    title: `Meeting ${processingStatus}`,
    created_at: null,
    updated_at: null,
    meeting_date: meetingDate,
    body_name: "City Council",
    status: processingStatus === "processed" ? "processed" : null,
    confidence_label: processingStatus === "processed" ? "high" : null,
    reader_low_confidence: false,
    detail_available: processingStatus === "processed",
    discovered_meeting:
      processingStatus === "processed"
        ? {
            discovered_meeting_id: "discovered-1",
            source_meeting_id: "71",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/71",
            discovered_at: "2026-03-10T12:00:00Z",
            synced_at: "2026-03-10T12:00:00Z",
          }
        : {
            discovered_meeting_id: "discovered-1",
            source_meeting_id: "71",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/71",
            discovered_at: "2026-03-10T12:00:00Z",
            synced_at: "2026-03-10T12:00:00Z",
          },
    processing: {
      processing_status: processingStatus,
      processing_status_updated_at: "2026-03-10T12:00:00Z",
      processing_request_id: null,
    },
  };
}

describe("meetings explorer helpers", () => {
  it("defaults the explorer flag on and honors explicit disable", () => {
    expect(isMeetingExplorerEnabled({})).toBe(true);
    expect(isMeetingExplorerEnabled({ [MEETING_EXPLORER_FLAG]: "false" })).toBe(false);
  });

  it("maps requestable and processed actions deterministically", () => {
    expect(canRequestMeetingSummary(buildMeeting("discovered"))).toBe(true);
    expect(canRequestMeetingSummary(buildMeeting("failed"))).toBe(true);
    expect(canRequestMeetingSummary(buildMeeting("queued"))).toBe(false);
    expect(canRequestMeetingSummary(buildMeeting("discovered", "2099-03-20"))).toBe(false);
    expect(getMeetingTileActionLabel(buildMeeting("processed"))).toBe("View briefing");
    expect(getMeetingTileBadgeLabel(buildMeeting("processing"))).toBe("Processing");
    expect(getMeetingTileStatusCopy(buildMeeting("queued"))).toContain("already active");
  });

  it("builds detail hrefs only for processed meetings and preserves return path", () => {
    expect(buildMeetingDetailHref(buildMeeting("discovered"), "/meetings?cursor=old")).toBeNull();
    expect(buildMeetingDetailHref(buildMeeting("processed"), "/meetings?cursor=old")).toBe(
      "/meetings/meeting-detail-1?returnTo=%2Fmeetings%3Fcursor%3Dold",
    );
  });

  it("accepts only local meetings return paths", () => {
    expect(resolveMeetingReturnPath("/meetings?cursor=old")).toBe("/meetings?cursor=old");
    expect(resolveMeetingReturnPath("https://example.org/elsewhere")).toBe("/meetings");
    expect(resolveMeetingReturnPath(undefined)).toBe("/meetings");
  });
});