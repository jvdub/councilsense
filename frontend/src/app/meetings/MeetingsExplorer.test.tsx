import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MeetingsApiError } from "../../lib/api/meetings";
import { MeetingsExplorer } from "./MeetingsExplorer";
import { type MeetingListItem } from "../../lib/models/meetings";

const createMeetingProcessingRequestMock = vi.fn();
const routerRefreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: routerRefreshMock,
  }),
}));

vi.mock("../../lib/api/meetings", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api/meetings")>(
    "../../lib/api/meetings",
  );
  return {
    ...actual,
    createMeetingProcessingRequest: (
      authToken: string,
      cityId: string,
      discoveredMeetingId: string,
    ) =>
      createMeetingProcessingRequestMock(
        authToken,
        cityId,
        discoveredMeetingId,
      ),
  };
});

function buildMeeting(
  id: string,
  status: MeetingListItem["processing"]["processing_status"],
): MeetingListItem {
  return {
    id,
    meeting_id: status === "processed" ? `detail-${id}` : null,
    city_id: "seattle-wa",
    city_name: "Seattle",
    meeting_uid: status === "processed" ? `uid-${id}` : null,
    title: `Meeting ${id}`,
    created_at: "2026-03-10T10:00:00Z",
    updated_at: "2026-03-10T10:00:00Z",
    meeting_date: "2026-03-20",
    body_name: "City Council",
    status: status === "processed" ? "processed" : null,
    confidence_label: status === "processed" ? "high" : null,
    reader_low_confidence: false,
    detail_available: status === "processed",
    discovered_meeting: {
      discovered_meeting_id: `discovered-${id}`,
      source_meeting_id: `${id}`,
      source_provider_name: "civicclerk",
      source_meeting_url: `https://example.org/meeting/${id}`,
      discovered_at: "2026-03-10T10:00:00Z",
      synced_at: "2026-03-10T10:00:00Z",
    },
    processing: {
      processing_status: status,
      processing_status_updated_at: "2026-03-10T10:00:00Z",
      processing_request_id:
        status === "queued" || status === "processing" || status === "failed"
          ? `req-${id}`
          : null,
    },
  };
}

describe("MeetingsExplorer", () => {
  beforeEach(() => {
    createMeetingProcessingRequestMock.mockReset();
    routerRefreshMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("renders deterministic tile variants across supported states", () => {
    render(
      <MeetingsExplorer
        authToken="token-1"
        cityId="seattle-wa"
        returnToPath="/meetings?cursor=cursor-a"
        initialItems={[
          buildMeeting("1", "discovered"),
          buildMeeting("2", "queued"),
          buildMeeting("3", "processing"),
          buildMeeting("4", "processed"),
          buildMeeting("5", "failed"),
        ]}
      />,
    );

    expect(screen.getByText("Ready to request")).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Briefing ready")).toBeInTheDocument();
    expect(screen.getByText("Needs retry")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request summary" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Meeting 4" })).toHaveAttribute(
      "href",
      "/meetings/detail-4?returnTo=%2Fmeetings%3Fcursor%3Dcursor-a",
    );
  });

  it("treats already-active request outcomes as a success path", async () => {
    createMeetingProcessingRequestMock.mockResolvedValueOnce({
      discovered_meeting_id: "discovered-1",
      meeting_id: null,
      processing: {
        processing_status: "processing",
        processing_status_updated_at: "2026-03-11T10:05:00Z",
        processing_request_id: "req-1",
        request_outcome: "already_active",
      },
    });

    render(
      <MeetingsExplorer
        authToken="token-1"
        cityId="seattle-wa"
        returnToPath="/meetings"
        initialItems={[buildMeeting("1", "discovered")]}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Request summary" }),
    );

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        "A summary request is already active for this meeting.",
      );
    });
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });

  it("surfaces limit errors without breaking tile state", async () => {
    createMeetingProcessingRequestMock.mockRejectedValueOnce(
      new MeetingsApiError(
        "Too many active on-demand processing requests for user",
        429,
      ),
    );

    render(
      <MeetingsExplorer
        authToken="token-1"
        cityId="seattle-wa"
        returnToPath="/meetings"
        initialItems={[buildMeeting("1", "discovered")]}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Request summary" }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "You already have several summary requests in progress. Try again after one finishes.",
      );
    });
    expect(
      screen.getByRole("button", { name: "Request summary" }),
    ).toBeEnabled();
  });

  it("polls for updates while queued or processing jobs are present", () => {
    vi.useFakeTimers();

    render(
      <MeetingsExplorer
        authToken="token-1"
        cityId="seattle-wa"
        returnToPath="/meetings"
        initialItems={[
          buildMeeting("2", "queued"),
          buildMeeting("3", "processing"),
        ]}
      />,
    );

    vi.advanceTimersByTime(5000);

    expect(routerRefreshMock).toHaveBeenCalledTimes(1);
  });

  it("does not poll when no active jobs are present", () => {
    vi.useFakeTimers();

    render(
      <MeetingsExplorer
        authToken="token-1"
        cityId="seattle-wa"
        returnToPath="/meetings"
        initialItems={[
          buildMeeting("1", "discovered"),
          buildMeeting("4", "processed"),
        ]}
      />,
    );

    vi.advanceTimersByTime(10000);

    expect(routerRefreshMock).not.toHaveBeenCalled();
  });
});
