import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../lib/api/bootstrap";
import { getAuthTokenFromCookie } from "../../lib/auth/session";
import { getOnboardingRedirectPath } from "../../lib/onboarding/guard";

export default async function MeetingsPage() {
  const authToken = await getAuthTokenFromCookie();

  if (!authToken) {
    redirect("/auth/sign-in");
  }

  const bootstrap = await fetchBootstrap(authToken);
  const redirectPath = getOnboardingRedirectPath(bootstrap, "/meetings");

  if (redirectPath) {
    redirect(redirectPath);
  }

  return <main><h1>Meetings</h1></main>;
}