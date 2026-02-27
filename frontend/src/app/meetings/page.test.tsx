import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MeetingsPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();

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

describe("MeetingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
  });

  it("renders meetings for returning users with onboarding complete", async () => {
    const bootstrap = {
      user_id: "user-returning",
      home_city_id: "seattle-wa",
      onboarding_required: false,
      supported_city_ids: ["seattle-wa", "portland-or"],
    };
    getAuthTokenFromCookieMock.mockResolvedValueOnce("token-abc");
    fetchBootstrapMock.mockResolvedValueOnce(bootstrap);
    getOnboardingRedirectPathMock.mockReturnValueOnce(null);

    render(await MeetingsPage());

    expect(
      screen.getByRole("heading", { name: "Meetings" }),
    ).toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
  });
});
