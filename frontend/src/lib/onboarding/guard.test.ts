import { describe, expect, it } from "vitest";

import { getOnboardingRedirectPath } from "./guard";

describe("getOnboardingRedirectPath", () => {
  it("redirects first-run users from meetings to onboarding", () => {
    const redirectPath = getOnboardingRedirectPath(
      {
        user_id: "user-1",
        home_city_id: null,
        onboarding_required: true,
        supported_city_ids: ["seattle-wa"],
      },
      "/meetings",
    );

    expect(redirectPath).toBe("/onboarding/city");
  });

  it("redirects returning users away from onboarding to meetings", () => {
    const redirectPath = getOnboardingRedirectPath(
      {
        user_id: "user-1",
        home_city_id: "seattle-wa",
        onboarding_required: false,
        supported_city_ids: ["seattle-wa"],
      },
      "/onboarding/city",
    );

    expect(redirectPath).toBe("/meetings");
  });

  it("keeps first-run users on onboarding route", () => {
    const redirectPath = getOnboardingRedirectPath(
      {
        user_id: "user-1",
        home_city_id: null,
        onboarding_required: true,
        supported_city_ids: ["seattle-wa"],
      },
      "/onboarding/city",
    );

    expect(redirectPath).toBeNull();
  });
});