import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const fetchProfileMock = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirectMock(path),
}));

vi.mock("../../lib/auth/session", () => ({
  getAuthTokenFromCookie: () => getAuthTokenFromCookieMock(),
}));

vi.mock("../../lib/api/bootstrap", () => ({
  fetchBootstrap: (authToken: string) => fetchBootstrapMock(authToken),
}));

vi.mock("../../lib/api/profile", () => ({
  fetchProfile: (authToken: string) => fetchProfileMock(authToken),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(SettingsPage()).rejects.toThrow("REDIRECT:/auth/sign-in");
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
    expect(fetchProfileMock).not.toHaveBeenCalled();
  });

  it("passes profile and city options to settings form", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce("token-abc");
    fetchBootstrapMock.mockResolvedValueOnce({
      user_id: "user-1",
      home_city_id: "seattle-wa",
      onboarding_required: false,
      supported_city_ids: ["seattle-wa", "portland-or"],
    });
    fetchProfileMock.mockResolvedValueOnce({
      email: "user@example.com",
      home_city_id: "seattle-wa",
      notifications_enabled: true,
      notifications_paused_until: null,
    });

    const page = await SettingsPage();

    expect(fetchBootstrapMock).toHaveBeenCalledWith("token-abc");
    expect(fetchProfileMock).toHaveBeenCalledWith("token-abc");
    expect(page.props.authToken).toBe("token-abc");
    expect(page.props.supportedCityIds).toEqual(["seattle-wa", "portland-or"]);
    expect(page.props.initialProfile).toEqual({
      email: "user@example.com",
      home_city_id: "seattle-wa",
      notifications_enabled: true,
      notifications_paused_until: null,
    });
    expect(redirectMock).not.toHaveBeenCalled();
  });
});