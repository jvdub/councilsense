"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, patchProfile, ProfileResponse } from "../../lib/api/profile";

type SettingsPreferencesFormProps = {
  authToken: string;
  supportedCityIds: string[];
  initialProfile: ProfileResponse;
};

function getPauseTimestamp(hoursFromNow: number): string {
  return new Date(Date.now() + hoursFromNow * 60 * 60 * 1000).toISOString();
}

export function SettingsPreferencesForm({
  authToken,
  supportedCityIds,
  initialProfile,
}: SettingsPreferencesFormProps) {
  const router = useRouter();
  const [homeCityId, setHomeCityId] = useState(initialProfile.home_city_id ?? "");
  const [notificationsEnabled, setNotificationsEnabled] = useState(initialProfile.notifications_enabled);
  const [notificationsPausedUntil, setNotificationsPausedUntil] = useState<string | null>(
    initialProfile.notifications_paused_until,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const cityOptions = useMemo(
    () => supportedCityIds.map((cityId) => ({ cityId, label: cityId })),
    [supportedCityIds],
  );

  async function applyUpdate(nextPausedUntil: string | null = notificationsPausedUntil) {
    if (!homeCityId) {
      setErrorMessage("Select a home city before saving.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const updatedProfile = await patchProfile(authToken, {
        home_city_id: homeCityId,
        notifications_enabled: notificationsEnabled,
        notifications_paused_until: nextPausedUntil,
      });
      setHomeCityId(updatedProfile.home_city_id ?? "");
      setNotificationsEnabled(updatedProfile.notifications_enabled);
      setNotificationsPausedUntil(updatedProfile.notifications_paused_until);
      setSuccessMessage("Preferences saved.");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setErrorMessage("Unable to save preferences. Check your values and try again.");
      } else {
        setErrorMessage("Unable to save preferences. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await applyUpdate();
  }

  async function onPauseFor24Hours() {
    const pauseUntil = getPauseTimestamp(24);
    await applyUpdate(pauseUntil);
  }

  async function onUnpause() {
    await applyUpdate(null);
  }

  return (
    <main>
      <h1>Settings</h1>
      <form onSubmit={onSubmit}>
        <label htmlFor="home-city">Home city</label>
        <select
          id="home-city"
          name="home-city"
          value={homeCityId}
          onChange={(event) => setHomeCityId(event.target.value)}
          disabled={isSubmitting}
        >
          <option value="">Select a city</option>
          {cityOptions.map((option) => (
            <option key={option.cityId} value={option.cityId}>
              {option.label}
            </option>
          ))}
        </select>

        <label htmlFor="notifications-enabled">
          <input
            id="notifications-enabled"
            name="notifications-enabled"
            type="checkbox"
            checked={notificationsEnabled}
            onChange={(event) => setNotificationsEnabled(event.target.checked)}
            disabled={isSubmitting}
          />
          Enable notifications
        </label>

        <p>
          Notifications paused until: {notificationsPausedUntil ?? "Not paused"}
        </p>

        <button type="button" onClick={onPauseFor24Hours} disabled={isSubmitting}>
          Pause for 24 hours
        </button>
        <button
          type="button"
          onClick={onUnpause}
          disabled={isSubmitting || notificationsPausedUntil === null}
        >
          Unpause
        </button>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Save preferences"}
        </button>
      </form>

      {successMessage ? <p role="status">{successMessage}</p> : null}
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
    </main>
  );
}