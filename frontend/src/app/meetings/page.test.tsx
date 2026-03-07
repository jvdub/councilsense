import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MeetingsPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();
const fetchCityMeetingsMock = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirectMock(path),
}));

vi.mock("../../lib/auth/session", () => ({
  getAuthTokenFromCookie: () => getAuthTokenFromCookieMock(),
}));

vi.mock("../../lib/api/bootstrap", () => ({
  fetchBootstrap: (authToken: string) => fetchBootstrapMock(authToken),
}));

vi.mock("../../lib/onboarding/guard", () => ({
  getOnboardingRedirectPath: (bootstrap: unknown, currentPath: string) =>
    getOnboardingRedirectPathMock(bootstrap, currentPath),
}));

vi.mock("../../lib/api/meetings", () => ({
  fetchCityMeetings: (
    authToken: string,
    cityId: string,
    filters?: Record<string, unknown>,
  ) => fetchCityMeetingsMock(authToken, cityId, filters),
}));

describe("MeetingsPage", () => {
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
    fetchCityMeetingsMock.mockReset();
    getAuthTokenFromCookieMock.mockResolvedValue("token-abc");
    fetchBootstrapMock.mockResolvedValue(returningBootstrap);
    getOnboardingRedirectPathMock.mockReturnValue(null);
  });

  afterEach(() => {
    cleanup();
  });

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(MeetingsPage()).rejects.toThrow("REDIRECT:/auth/sign-in");
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
  });

  it("redirects first-run authenticated users to onboarding", async () => {
    const bootstrap = {
      user_id: "user-first-run",
      home_city_id: null,
      onboarding_required: true,
      supported_city_ids: ["seattle-wa", "portland-or"],
    };
    getAuthTokenFromCookieMock.mockResolvedValueOnce("token-123");
    fetchBootstrapMock.mockResolvedValueOnce(bootstrap);
    getOnboardingRedirectPathMock.mockReturnValueOnce("/onboarding/city");

    await expect(MeetingsPage()).rejects.toThrow("REDIRECT:/onboarding/city");
    expect(fetchBootstrapMock).toHaveBeenCalledWith("token-123");
    expect(getOnboardingRedirectPathMock).toHaveBeenCalledWith(
      bootstrap,
      "/meetings",
    );
    expect(fetchCityMeetingsMock).not.toHaveBeenCalled();
  });

  it("redirects to meeting detail when meeting_id deep-link is present", async () => {
    await expect(
      MeetingsPage({
        searchParams: Promise.resolve({
          meeting_id: "meeting-42",
        }),
      }),
    ).rejects.toThrow("REDIRECT:/meetings/meeting-42");

    expect(fetchCityMeetingsMock).not.toHaveBeenCalled();
  });

  it("keeps meetings list flow when meeting_id deep-link is blank", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      limit: 20,
    });

    render(
      await MeetingsPage({
        searchParams: Promise.resolve({
          meeting_id: "   ",
        }),
      }),
    );

    expect(fetchCityMeetingsMock).toHaveBeenCalledWith("token-abc", "seattle-wa", {
      cursor: undefined,
      limit: 20,
    });
    expect(screen.getByText("No meetings found for your city yet.")).toBeInTheDocument();
  });

  it("renders meetings list rows with status and confidence metadata", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-1",
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: "uid-1",
          title: "Budget Committee",
          created_at: "2026-02-25 18:00:00",
          updated_at: "2026-02-25 19:00:00",
          meeting_date: "2026-02-25",
          body_name: "City Council",
          status: "processed",
          confidence_label: "high",
          reader_low_confidence: false,
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(screen.getByRole("heading", { name: "Meetings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Budget Committee" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Budget Committee" })).toHaveAttribute(
      "href",
      "/meetings/meeting-1",
    );
    expect(screen.getByText("Seattle • City Council • February 25, 2026")).toBeInTheDocument();
    expect(screen.getByText("Status: Processed · Confidence: High")).toBeInTheDocument();
    expect(screen.getByText("Meeting date: February 25, 2026")).toBeInTheDocument();
    expect(fetchCityMeetingsMock).toHaveBeenCalledWith("token-abc", "seattle-wa", {
      cursor: undefined,
      limit: 20,
    });
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("renders limited-confidence label for low-confidence meetings", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-lc-1",
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: "uid-lc-1",
          title: "Public Safety Committee",
          created_at: "2026-02-24 17:00:00",
          updated_at: "2026-02-24 18:00:00",
          meeting_date: "2026-02-24",
          body_name: "Public Safety Committee",
          status: "limited_confidence",
          confidence_label: "limited_confidence",
          reader_low_confidence: true,
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(
      screen.getByText("Status: Limited Confidence · Confidence: Limited Confidence"),
    ).toBeInTheDocument();
  });

  it("renders an empty state when no meetings are returned", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(screen.getByText("No meetings found for your city yet.")).toBeInTheDocument();
  });

  it("renders an error state when list fetch fails", async () => {
    fetchCityMeetingsMock.mockRejectedValueOnce(new Error("Service unavailable"));

    render(await MeetingsPage());

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Unable to load meetings. Service unavailable")).toBeInTheDocument();
  });

  it("shows pagination links and preserves cursor continuity", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-2",
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: "uid-2",
          title: "City Council Session",
          created_at: "2026-02-24 17:00:00",
          updated_at: "2026-02-24 18:00:00",
          meeting_date: "2026-02-24",
          body_name: "City Council",
          status: "limited_confidence",
          confidence_label: "limited_confidence",
          reader_low_confidence: true,
        },
      ],
      next_cursor: "cursor-next",
      limit: 10,
    });

    render(
      await MeetingsPage({
        searchParams: Promise.resolve({
          cursor: "cursor-current",
          prev: "cursor-prev",
          limit: "10",
        }),
      }),
    );

    expect(fetchCityMeetingsMock).toHaveBeenCalledWith("token-abc", "seattle-wa", {
      cursor: "cursor-current",
      limit: 10,
    });
    expect(screen.getByRole("link", { name: "Load newer meetings" })).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-prev&limit=10",
    );
    expect(screen.getByRole("link", { name: "Load older meetings" })).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-next&prev=cursor-current&limit=10",
    );
  });
});
