import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MeetingDetailPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();
const fetchMeetingDetailMock = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirectMock(path),
}));

vi.mock("../../../lib/auth/session", () => ({
  getAuthTokenFromCookie: () => getAuthTokenFromCookieMock(),
}));

vi.mock("../../../lib/api/bootstrap", () => ({
  fetchBootstrap: (authToken: string) => fetchBootstrapMock(authToken),
}));

vi.mock("../../../lib/onboarding/guard", () => ({
  getOnboardingRedirectPath: (bootstrap: unknown, currentPath: string) =>
    getOnboardingRedirectPathMock(bootstrap, currentPath),
}));

vi.mock("../../../lib/api/meetings", () => ({
  fetchMeetingDetail: (authToken: string, meetingId: string) =>
    fetchMeetingDetailMock(authToken, meetingId),
}));

describe("MeetingDetailPage", () => {
  const returningBootstrap = {
    user_id: "user-returning",
    home_city_id: "seattle-wa",
    onboarding_required: false,
    supported_city_ids: ["seattle-wa", "portland-or"],
  };

  beforeEach(() => {
    redirectMock.mockClear();
    getAuthTokenFromCookieMock.mockReset();
    fetchBootstrapMock.mockReset();
    getOnboardingRedirectPathMock.mockReset();
    fetchMeetingDetailMock.mockReset();
    getAuthTokenFromCookieMock.mockResolvedValue("token-abc");
    fetchBootstrapMock.mockResolvedValue(returningBootstrap);
    getOnboardingRedirectPathMock.mockReturnValue(null);
  });

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(
      MeetingDetailPage({ params: Promise.resolve({ meetingId: "meeting-1" }) }),
    ).rejects.toThrow("REDIRECT:/auth/sign-in");
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
  });

  it("renders summary, decisions, topics, and evidence references", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-1",
      city_id: "seattle-wa",
      meeting_uid: "uid-1",
      title: "Council Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-1",
      published_at: "2026-02-25 19:00:00",
      summary: "Council approved the downtown transit plan.",
      key_decisions: ["Approved downtown transit plan"],
      key_actions: ["Staff to publish implementation timeline"],
      notable_topics: ["Transit", "Budget"],
      claims: [
        {
          id: "claim-1",
          claim_order: 1,
          claim_text: "Council approved the transit plan.",
          evidence: [
            {
              id: "pointer-1",
              artifact_id: "artifact-1",
              section_ref: "minutes.section.4",
              char_start: 12,
              char_end: 80,
              excerpt: "Council voted 6-1 to approve the transit plan.",
            },
          ],
        },
      ],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-1" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Council Session" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument();
    expect(screen.getByText("Council approved the downtown transit plan.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decisions and actions" })).toBeInTheDocument();
    expect(screen.getByText("Approved downtown transit plan")).toBeInTheDocument();
    expect(screen.getByText("Staff to publish implementation timeline")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Notable topics" })).toBeInTheDocument();
    expect(screen.getByText("Transit")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence references" })).toBeInTheDocument();
    expect(screen.getByText("Council approved the transit plan.")).toBeInTheDocument();
    expect(screen.getByText("Council voted 6-1 to approve the transit plan.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "minutes.section.4" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to meetings" })).toHaveAttribute(
      "href",
      "/meetings",
    );
    expect(fetchMeetingDetailMock).toHaveBeenCalledWith("token-abc", "meeting-1");
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("renders a prominent limited confidence banner when flagged", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-2",
      city_id: "seattle-wa",
      meeting_uid: "uid-2",
      title: "Budget Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "limited_confidence",
      confidence_label: "limited_confidence",
      reader_low_confidence: true,
      publication_id: null,
      published_at: null,
      summary: null,
      key_decisions: [],
      key_actions: [],
      notable_topics: [],
      claims: [],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-2" }),
      }),
    );

    expect(screen.getByRole("alert", { name: "Confidence warning" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limited confidence" })).toBeInTheDocument();
    expect(screen.getByText("Summary is not available yet.")).toBeInTheDocument();
    expect(screen.getByText("No key decisions available.")).toBeInTheDocument();
    expect(screen.getByText("No key actions available.")).toBeInTheDocument();
    expect(screen.getByText("No notable topics available.")).toBeInTheDocument();
    expect(screen.getByText("No evidence references available.")).toBeInTheDocument();
  });

  it("renders an error state when detail fetch fails", async () => {
    fetchMeetingDetailMock.mockRejectedValueOnce(new Error("Service unavailable"));

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-3" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Meeting detail" })).toBeInTheDocument();
    expect(
      screen.getByText("Unable to load meeting detail. Service unavailable"),
    ).toBeInTheDocument();
  });
});
