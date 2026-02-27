import { beforeEach, describe, expect, it, vi } from "vitest";

import OnboardingCityPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();

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

describe("OnboardingCityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(OnboardingCityPage()).rejects.toThrow(
      "REDIRECT:/auth/sign-in",
    );
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
  });

  it("redirects returning users with completed onboarding to meetings", async () => {
    const bootstrap = {
      user_id: "user-returning",
      home_city_id: "seattle-wa",
      onboarding_required: false,
      supported_city_ids: ["seattle-wa", "portland-or"],
    };
    getAuthTokenFromCookieMock.mockResolvedValueOnce("token-abc");
    fetchBootstrapMock.mockResolvedValueOnce(bootstrap);
    getOnboardingRedirectPathMock.mockReturnValueOnce("/meetings");

    await expect(OnboardingCityPage()).rejects.toThrow("REDIRECT:/meetings");
    expect(fetchBootstrapMock).toHaveBeenCalledWith("token-abc");
    expect(getOnboardingRedirectPathMock).toHaveBeenCalledWith(
      bootstrap,
      "/onboarding/city",
    );
  });

  it("returns city selection form for first-run users", async () => {
    const bootstrap = {
      user_id: "user-first-run",
      home_city_id: null,
      onboarding_required: true,
      supported_city_ids: ["seattle-wa", "portland-or"],
    };
    getAuthTokenFromCookieMock.mockResolvedValueOnce("token-new");
    fetchBootstrapMock.mockResolvedValueOnce(bootstrap);
    getOnboardingRedirectPathMock.mockReturnValueOnce(null);

    const page = await OnboardingCityPage();

    expect(page.props.authToken).toBe("token-new");
    expect(page.props.cityIds).toEqual(["seattle-wa", "portland-or"]);
    expect(redirectMock).not.toHaveBeenCalled();
  });
});
