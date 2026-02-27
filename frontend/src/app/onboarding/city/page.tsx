import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../../lib/api/bootstrap";
import { getAuthTokenFromCookie } from "../../../lib/auth/session";
import { getOnboardingRedirectPath } from "../../../lib/onboarding/guard";
import { CitySelectionForm } from "./CitySelectionForm";

export default async function OnboardingCityPage() {
  const authToken = await getAuthTokenFromCookie();

  if (!authToken) {
    redirect("/auth/sign-in");
  }

  const bootstrap = await fetchBootstrap(authToken);
  const redirectPath = getOnboardingRedirectPath(bootstrap, "/onboarding/city");

  if (redirectPath) {
    redirect(redirectPath);
  }

  return <CitySelectionForm authToken={authToken} cityIds={bootstrap.supported_city_ids} />;
}