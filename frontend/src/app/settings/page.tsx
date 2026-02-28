import React from "react";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../lib/api/bootstrap";
import { fetchProfile } from "../../lib/api/profile";
import { getAuthTokenFromCookie } from "../../lib/auth/session";
import { SettingsPreferencesForm } from "./SettingsPreferencesForm";

export default async function SettingsPage() {
  const authToken = await getAuthTokenFromCookie();

  if (!authToken) {
    redirect("/auth/sign-in");
  }

  const [bootstrap, profile] = await Promise.all([
    fetchBootstrap(authToken),
    fetchProfile(authToken),
  ]);

  return (
    <SettingsPreferencesForm
      authToken={authToken}
      supportedCityIds={bootstrap.supported_city_ids}
      initialProfile={profile}
    />
  );
}