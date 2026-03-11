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
const routerRefreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirectMock(path),
  useRouter: () => ({
    refresh: routerRefreshMock,
  }),
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
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-10T12:00:00Z"));
    redirectMock.mockClear();
    getAuthTokenFromCookieMock.mockReset();
    fetchBootstrapMock.mockReset();
    getOnboardingRedirectPathMock.mockReset();
    fetchCityMeetingsMock.mockReset();
    routerRefreshMock.mockReset();
    getAuthTokenFromCookieMock.mockResolvedValue("token-abc");
    fetchBootstrapMock.mockResolvedValue(returningBootstrap);
    getOnboardingRedirectPathMock.mockReturnValue(null);
    delete process.env.NEXT_PUBLIC_ST039_UI_MEETING_EXPLORER_ENABLED;
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
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

    expect(fetchCityMeetingsMock).toHaveBeenCalledWith(
      "token-abc",
      "seattle-wa",
      {
        cursor: undefined,
        limit: 20,
      },
    );
    expect(
      screen.getByText("No past or current meetings found for your city yet."),
    ).toBeInTheDocument();
  });

  it("hides future meetings by default and offers an override link", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-current-1",
          meeting_id: null,
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: null,
          title: "Current Council Meeting",
          created_at: null,
          updated_at: "2026-03-10T09:00:00Z",
          meeting_date: "2026-03-10",
          body_name: "City Council",
          status: null,
          confidence_label: null,
          reader_low_confidence: false,
          detail_available: false,
          discovered_meeting: {
            discovered_meeting_id: "discovered-current-1",
            source_meeting_id: "100",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/100",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "discovered",
            processing_status_updated_at: "2026-03-10T10:00:00Z",
            processing_request_id: null,
          },
        },
        {
          id: "meeting-future-1",
          meeting_id: null,
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: null,
          title: "Future Council Meeting",
          created_at: null,
          updated_at: "2026-03-10T09:00:00Z",
          meeting_date: "2026-03-20",
          body_name: "City Council",
          status: null,
          confidence_label: null,
          reader_low_confidence: false,
          detail_available: false,
          discovered_meeting: {
            discovered_meeting_id: "discovered-future-1",
            source_meeting_id: "101",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/101",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "discovered",
            processing_status_updated_at: "2026-03-10T10:00:00Z",
            processing_request_id: null,
          },
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(
      screen.getByRole("heading", { name: "Current Council Meeting" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Future Council Meeting" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Show upcoming meetings" }),
    ).toHaveAttribute("href", "/meetings?show_future=true");
  });

  it("shows an unavailable state instead of a no-op upcoming toggle when no future meetings exist", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-past-1",
          meeting_id: null,
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: null,
          title: "Past Council Meeting",
          created_at: null,
          updated_at: "2026-03-10T09:00:00Z",
          meeting_date: "2026-03-09",
          body_name: "City Council",
          status: null,
          confidence_label: null,
          reader_low_confidence: false,
          detail_available: false,
          discovered_meeting: {
            discovered_meeting_id: "discovered-past-1",
            source_meeting_id: "105",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/105",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "discovered",
            processing_status_updated_at: "2026-03-10T10:00:00Z",
            processing_request_id: null,
          },
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(
      screen.getByText("No future meetings with published agendas yet"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Show upcoming meetings" }),
    ).not.toBeInTheDocument();
  });

  it("backfills additional pages when hidden future meetings consume the first page", async () => {
    fetchCityMeetingsMock
      .mockResolvedValueOnce({
        items: [
          {
            id: "meeting-future-1",
            meeting_id: null,
            city_id: "seattle-wa",
            city_name: "Seattle",
            meeting_uid: null,
            title: "Future Council Meeting",
            created_at: null,
            updated_at: "2026-03-10T09:00:00Z",
            meeting_date: "2026-03-20",
            body_name: "City Council",
            status: null,
            confidence_label: null,
            reader_low_confidence: false,
            detail_available: false,
            discovered_meeting: {
              discovered_meeting_id: "discovered-future-1",
              source_meeting_id: "101",
              source_provider_name: "civicclerk",
              source_meeting_url: "https://example.org/meeting/101",
              discovered_at: "2026-03-10T10:00:00Z",
              synced_at: "2026-03-10T10:00:00Z",
            },
            processing: {
              processing_status: "discovered",
              processing_status_updated_at: "2026-03-10T10:00:00Z",
              processing_request_id: null,
            },
          },
        ],
        next_cursor: "cursor-next-1",
        limit: 1,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: "meeting-recent-1",
            meeting_id: null,
            city_id: "seattle-wa",
            city_name: "Seattle",
            meeting_uid: null,
            title: "Recent Council Meeting",
            created_at: null,
            updated_at: "2026-03-10T09:00:00Z",
            meeting_date: "2026-03-09",
            body_name: "City Council",
            status: null,
            confidence_label: null,
            reader_low_confidence: false,
            detail_available: false,
            discovered_meeting: {
              discovered_meeting_id: "discovered-recent-1",
              source_meeting_id: "102",
              source_provider_name: "civicclerk",
              source_meeting_url: "https://example.org/meeting/102",
              discovered_at: "2026-03-10T10:00:00Z",
              synced_at: "2026-03-10T10:00:00Z",
            },
            processing: {
              processing_status: "discovered",
              processing_status_updated_at: "2026-03-10T10:00:00Z",
              processing_request_id: null,
            },
          },
        ],
        next_cursor: null,
        limit: 1,
      });

    render(
      await MeetingsPage({
        searchParams: Promise.resolve({
          limit: "1",
        }),
      }),
    );

    expect(fetchCityMeetingsMock).toHaveBeenNthCalledWith(
      1,
      "token-abc",
      "seattle-wa",
      {
        cursor: undefined,
        limit: 1,
      },
    );
    expect(fetchCityMeetingsMock).toHaveBeenNthCalledWith(
      2,
      "token-abc",
      "seattle-wa",
      {
        cursor: "cursor-next-1",
        limit: 1,
      },
    );
    expect(
      screen.getByRole("heading", { name: "Recent Council Meeting" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Future Council Meeting" }),
    ).not.toBeInTheDocument();
  });

  it("shows future meetings when the filter override is enabled", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-future-1",
          meeting_id: null,
          city_id: "seattle-wa",
          city_name: "Seattle",
          meeting_uid: null,
          title: "Future Council Meeting",
          created_at: null,
          updated_at: "2026-03-10T09:00:00Z",
          meeting_date: "2026-03-20",
          body_name: "City Council",
          status: null,
          confidence_label: null,
          reader_low_confidence: false,
          detail_available: false,
          discovered_meeting: {
            discovered_meeting_id: "discovered-future-1",
            source_meeting_id: "101",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/101",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "discovered",
            processing_status_updated_at: "2026-03-10T10:00:00Z",
            processing_request_id: null,
          },
        },
      ],
      next_cursor: "cursor-next",
      limit: 10,
    });

    render(
      await MeetingsPage({
        searchParams: Promise.resolve({
          show_future: "true",
          cursor: "cursor-current",
          prev: "cursor-prev",
          limit: "10",
        }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Future Council Meeting" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Hide upcoming meetings" }),
    ).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-current&prev=cursor-prev&limit=10",
    );
    expect(
      screen.getByRole("link", { name: "Load newer meetings" }),
    ).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-prev&limit=10&show_future=true",
    );
    expect(
      screen.getByRole("link", { name: "Load older meetings" }),
    ).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-next&prev=cursor-current&limit=10&show_future=true",
    );
  });

  it("renders meetings list rows with status and confidence metadata", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-1",
          meeting_id: "meeting-1",
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
          detail_available: true,
          discovered_meeting: {
            discovered_meeting_id: "discovered-1",
            source_meeting_id: "71",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/71",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "processed",
            processing_status_updated_at: "2026-02-25 19:00:00",
            processing_request_id: null,
          },
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(
      screen.getByRole("heading", { name: "Meetings" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Budget Committee" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Budget Committee" }),
    ).toHaveAttribute("href", "/meetings/meeting-1");
    expect(
      screen.getByText("Seattle • City Council • February 25, 2026"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("A briefing is ready to open for this meeting."),
    ).toBeInTheDocument();
    expect(screen.getByText("Briefing ready")).toBeInTheDocument();
    expect(
      screen.getByText("Meeting date: February 25, 2026"),
    ).toBeInTheDocument();
    expect(fetchCityMeetingsMock).toHaveBeenCalledWith(
      "token-abc",
      "seattle-wa",
      {
        cursor: undefined,
        limit: 20,
      },
    );
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("renders limited-confidence label for low-confidence meetings", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-lc-1",
          meeting_id: "meeting-lc-1",
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
          detail_available: true,
          discovered_meeting: {
            discovered_meeting_id: "discovered-lc-1",
            source_meeting_id: "72",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/72",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "processed",
            processing_status_updated_at: "2026-02-24 18:00:00",
            processing_request_id: null,
          },
        },
      ],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(screen.getByText("Briefing ready")).toBeInTheDocument();
  });

  it("renders an empty state when no meetings are returned", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      limit: 20,
    });

    render(await MeetingsPage());

    expect(
      screen.getByText("No past or current meetings found for your city yet."),
    ).toBeInTheDocument();
  });

  it("renders an error state when list fetch fails", async () => {
    fetchCityMeetingsMock.mockRejectedValueOnce(
      new Error("Service unavailable"),
    );

    render(await MeetingsPage());

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByText("Unable to load meetings. Service unavailable"),
    ).toBeInTheDocument();
  });

  it("shows pagination links and preserves cursor continuity", async () => {
    fetchCityMeetingsMock.mockResolvedValueOnce({
      items: [
        {
          id: "meeting-2",
          meeting_id: "meeting-2",
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
          detail_available: true,
          discovered_meeting: {
            discovered_meeting_id: "discovered-2",
            source_meeting_id: "73",
            source_provider_name: "civicclerk",
            source_meeting_url: "https://example.org/meeting/73",
            discovered_at: "2026-03-10T10:00:00Z",
            synced_at: "2026-03-10T10:00:00Z",
          },
          processing: {
            processing_status: "processed",
            processing_status_updated_at: "2026-02-24 18:00:00",
            processing_request_id: null,
          },
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

    expect(fetchCityMeetingsMock).toHaveBeenCalledWith(
      "token-abc",
      "seattle-wa",
      {
        cursor: "cursor-current",
        limit: 10,
      },
    );
    expect(
      screen.getByRole("link", { name: "Load newer meetings" }),
    ).toHaveAttribute("href", "/meetings?cursor=cursor-prev&limit=10");
    expect(
      screen.getByRole("link", { name: "Load older meetings" }),
    ).toHaveAttribute(
      "href",
      "/meetings?cursor=cursor-next&prev=cursor-current&limit=10",
    );
  });

  it("preserves the current explorer path when deep-linking to a processed meeting", async () => {
    await expect(
      MeetingsPage({
        searchParams: Promise.resolve({
          meeting_id: "meeting-42",
          cursor: "cursor-current",
          prev: "cursor-prev",
          limit: "10",
        }),
      }),
    ).rejects.toThrow(
      "REDIRECT:/meetings/meeting-42?returnTo=%2Fmeetings%3Fcursor%3Dcursor-current%26prev%3Dcursor-prev%26limit%3D10",
    );
  });
});
