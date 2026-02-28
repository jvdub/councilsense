"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, patchProfile, ProfileResponse } from "../../lib/api/profile";

type SettingsPreferencesFormProps = {
  authToken: string;
  supportedCityIds: string[];
  initialProfile: ProfileResponse;
};

type BrowserPermissionState = "granted" | "denied" | "default";

function getPauseTimestamp(hoursFromNow: number): string {
  return new Date(Date.now() + hoursFromNow * 60 * 60 * 1000).toISOString();
}

function decodeBase64Url(value: string): Uint8Array {
  const withPadding = `${value}${"=".repeat((4 - (value.length % 4)) % 4)}`;
  const base64 = withPadding.replace(/-/g, "+").replace(/_/g, "/");
  const decoded = atob(base64);
  const bytes = new Uint8Array(decoded.length);

  for (let index = 0; index < decoded.length; index += 1) {
    bytes[index] = decoded.charCodeAt(index);
  }

  return bytes;
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
  const [isPushSupported, setIsPushSupported] = useState(false);
  const [pushPermission, setPushPermission] = useState<BrowserPermissionState | null>(null);
  const [isPushSubscribed, setIsPushSubscribed] = useState(false);
  const [isPushSubmitting, setIsPushSubmitting] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [pushErrorMessage, setPushErrorMessage] = useState<string | null>(null);

  const cityOptions = useMemo(
    () => supportedCityIds.map((cityId) => ({ cityId, label: cityId })),
    [supportedCityIds],
  );

  useEffect(() => {
    const supportsPush =
      typeof window !== "undefined" &&
      typeof navigator.serviceWorker !== "undefined" &&
      typeof window.PushManager !== "undefined" &&
      typeof window.Notification !== "undefined";

    setIsPushSupported(supportsPush);

    if (!supportsPush) {
      return;
    }

    setPushPermission(Notification.permission);

    void (async () => {
      const registration = await navigator.serviceWorker.getRegistration();
      const existingSubscription = await registration?.pushManager.getSubscription();
      setIsPushSubscribed(Boolean(existingSubscription));
    })();
  }, []);

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

  async function onSubscribePush() {
    if (!isPushSupported || pushPermission === "denied") {
      return;
    }

    setIsPushSubmitting(true);
    setPushErrorMessage(null);
    setPushMessage(null);

    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      let permission = Notification.permission;

      if (permission === "default") {
        permission = await Notification.requestPermission();
      }

      setPushPermission(permission);

      if (permission !== "granted") {
        setPushErrorMessage(
          "Push permission is blocked. Enable notifications in your browser settings to subscribe.",
        );
        return;
      }

      const existingSubscription = await registration.pushManager.getSubscription();
      if (existingSubscription) {
        setIsPushSubscribed(true);
        setPushMessage("Push is already enabled on this device.");
        return;
      }

      const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        setPushErrorMessage("Push is not configured for this environment.");
        return;
      }

      await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: decodeBase64Url(vapidPublicKey),
      });

      setIsPushSubscribed(true);
      setPushMessage("Push enabled on this device.");
    } catch {
      setPushErrorMessage("Unable to enable push on this device. Try again.");
    } finally {
      setIsPushSubmitting(false);
    }
  }

  async function onUnsubscribePush() {
    if (!isPushSupported) {
      return;
    }

    setIsPushSubmitting(true);
    setPushErrorMessage(null);
    setPushMessage(null);

    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const existingSubscription = await registration?.pushManager.getSubscription();

      if (existingSubscription) {
        await existingSubscription.unsubscribe();
      }

      setIsPushSubscribed(false);
      setPushMessage("Push disabled on this device.");
    } catch {
      setPushErrorMessage("Unable to disable push on this device. Try again.");
    } finally {
      setIsPushSubmitting(false);
    }
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

      <section aria-label="Push notifications">
        <h2>Push notifications</h2>
        {!isPushSupported ? (
          <p>Push is not supported in this browser. You can still manage notification preferences above.</p>
        ) : (
          <>
            <p>Permission: {pushPermission ?? "default"}</p>
            <p>Device subscription: {isPushSubscribed ? "Enabled" : "Not enabled"}</p>
            {pushPermission === "denied" ? (
              <p>Push is blocked by browser permission. Enable notifications in browser settings, then retry.</p>
            ) : null}
            <button
              type="button"
              onClick={onSubscribePush}
              disabled={isPushSubmitting || isPushSubscribed || pushPermission === "denied"}
            >
              {isPushSubmitting ? "Updating push..." : "Enable push on this device"}
            </button>
            <button
              type="button"
              onClick={onUnsubscribePush}
              disabled={isPushSubmitting || !isPushSubscribed}
            >
              Disable push on this device
            </button>
          </>
        )}
      </section>

      {successMessage ? <p role="status">{successMessage}</p> : null}
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {pushMessage ? <p role="status">{pushMessage}</p> : null}
      {pushErrorMessage ? <p role="alert">{pushErrorMessage}</p> : null}
    </main>
  );
}