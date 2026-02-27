import type { BootstrapResponse } from "../api/bootstrap";

export function getOnboardingRedirectPath(
  bootstrap: BootstrapResponse,
  currentPath: "/onboarding/city" | "/meetings",
): "/onboarding/city" | "/meetings" | null {
  if (bootstrap.onboarding_required && currentPath !== "/onboarding/city") {
    return "/onboarding/city";
  }

  if (!bootstrap.onboarding_required && currentPath === "/onboarding/city") {
    return "/meetings";
  }

  return null;
}