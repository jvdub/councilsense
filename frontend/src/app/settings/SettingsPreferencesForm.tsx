"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, patchProfile, ProfileResponse } from "../../lib/api/profile";
import {
  createDeletionRequest,
  createExportRequest,
  getDeletionRequest,
  getExportRequest,
  GovernanceApiError,
  type DeletionRequestMode,
  type DeletionRequestRecord,
  type ExportRequestRecord,
} from "../../lib/api/governance";
import {
  createOrRefreshPushSubscription,
  deletePushSubscription,
  listPushSubscriptions,
  type PushSubscriptionServerStatus,
} from "../../lib/api/pushSubscriptions";
import {
  mapPushCapabilityState,
  mapPushRecoveryAction,
  type BrowserPermissionState,
} from "../../lib/push/subscriptionState";
import { LegalLinks } from "../LegalLinks";

type SettingsPreferencesFormProps = {
  authToken: string;
  supportedCityIds: string[];
  initialProfile: ProfileResponse;
};

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

function createIdempotencyKey(prefix: "export" | "deletion") {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}`;
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
  const [pushSubscriptionId, setPushSubscriptionId] = useState<string | null>(null);
  const [pushServerStatus, setPushServerStatus] = useState<PushSubscriptionServerStatus | null>(null);
  const [isPushSubmitting, setIsPushSubmitting] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [pushErrorMessage, setPushErrorMessage] = useState<string | null>(null);
  const [exportRequest, setExportRequest] = useState<ExportRequestRecord | null>(null);
  const [deletionRequest, setDeletionRequest] = useState<DeletionRequestRecord | null>(null);
  const [deletionMode, setDeletionMode] = useState<DeletionRequestMode>("anonymize");
  const [deletionConfirmChecked, setDeletionConfirmChecked] = useState(false);
  const [isGovernanceSubmitting, setIsGovernanceSubmitting] = useState(false);
  const [governanceMessage, setGovernanceMessage] = useState<string | null>(null);
  const [governanceErrorMessage, setGovernanceErrorMessage] = useState<string | null>(null);

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
      try {
        const registration = await navigator.serviceWorker.getRegistration();
        const existingSubscription = await registration?.pushManager.getSubscription();
        const endpoint = existingSubscription?.endpoint ?? null;
        setIsPushSubscribed(Boolean(existingSubscription));

        const backendSubscriptions = await listPushSubscriptions(authToken);
        const matchingSubscription = endpoint
          ? backendSubscriptions.items.find((item) => item.endpoint === endpoint) ?? null
          : null;

        if (matchingSubscription) {
          setPushSubscriptionId(matchingSubscription.id);
          setPushServerStatus(matchingSubscription.status);
          return;
        }

        setPushSubscriptionId(null);
        setPushServerStatus(null);
      } catch {
        setPushSubscriptionId(null);
        setPushServerStatus(null);
      }
    })();
  }, [authToken]);

  const pushCapabilityState = mapPushCapabilityState(isPushSupported, pushPermission);
  const pushRecoveryAction = mapPushRecoveryAction(pushServerStatus);

  async function syncBackendSubscription(endpoint: string): Promise<void> {
    const subscriptions = await listPushSubscriptions(authToken);
    const matchingSubscription = subscriptions.items.find((item) => item.endpoint === endpoint) ?? null;

    if (matchingSubscription) {
      setPushSubscriptionId(matchingSubscription.id);
      setPushServerStatus(matchingSubscription.status);
      return;
    }

    setPushSubscriptionId(null);
    setPushServerStatus(null);
  }

  async function upsertSubscriptionForDevice(subscription: PushSubscription): Promise<void> {
    const serialized = subscription.toJSON();
    const p256dh = serialized.keys?.p256dh;
    const auth = serialized.keys?.auth;

    if (!p256dh || !auth) {
      throw new Error("Push subscription keys missing");
    }

    const response = await createOrRefreshPushSubscription(authToken, {
      endpoint: subscription.endpoint,
      keys: {
        p256dh,
        auth,
      },
      user_agent: navigator.userAgent,
    });

    setPushSubscriptionId(response.id);
    setPushServerStatus(response.status);
  }

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
    if (pushCapabilityState === "unsupported" || pushCapabilityState === "permission_denied") {
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
      let subscription = existingSubscription;

      if (!subscription) {
        const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
        if (!vapidPublicKey) {
          setPushErrorMessage("Push is not configured for this environment.");
          return;
        }

        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeBase64Url(vapidPublicKey),
        });
      }

      await upsertSubscriptionForDevice(subscription);

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
      const endpoint = existingSubscription?.endpoint ?? null;

      if (existingSubscription) {
        await existingSubscription.unsubscribe();
      }

      if (pushSubscriptionId) {
        await deletePushSubscription(authToken, pushSubscriptionId);
      } else if (endpoint) {
        const subscriptions = await listPushSubscriptions(authToken);
        const matchingSubscription = subscriptions.items.find((item) => item.endpoint === endpoint) ?? null;

        if (matchingSubscription) {
          await deletePushSubscription(authToken, matchingSubscription.id);
        }
      }

      setIsPushSubscribed(false);
      setPushSubscriptionId(null);
      setPushServerStatus(null);
      setPushMessage("Push disabled on this device.");
    } catch {
      setPushErrorMessage("Unable to disable push on this device. Try again.");
    } finally {
      setIsPushSubmitting(false);
    }
  }

  async function onRecoverPush() {
    if (!pushRecoveryAction) {
      return;
    }

    if (pushRecoveryAction === "reactivate") {
      await onUnsubscribePush();
    }

    await onSubscribePush();

    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const existingSubscription = await registration?.pushManager.getSubscription();
      if (existingSubscription) {
        await syncBackendSubscription(existingSubscription.endpoint);
      }
      setPushMessage("Push recovery completed on this device.");
    } catch {
      setPushErrorMessage("Unable to refresh push recovery state. Try again.");
    }
  }

  async function onRequestExport() {
    setIsGovernanceSubmitting(true);
    setGovernanceMessage(null);
    setGovernanceErrorMessage(null);

    try {
      const record = await createExportRequest(authToken, {
        idempotency_key: createIdempotencyKey("export"),
      });
      setExportRequest(record);
      setGovernanceMessage("Export request submitted.");
    } catch (error) {
      if (error instanceof GovernanceApiError && error.status === 422) {
        setGovernanceErrorMessage("Unable to submit export request. Check request details and try again.");
      } else {
        setGovernanceErrorMessage("Unable to submit export request. Try again.");
      }
    } finally {
      setIsGovernanceSubmitting(false);
    }
  }

  async function onRefreshExportStatus() {
    if (!exportRequest) {
      return;
    }

    setIsGovernanceSubmitting(true);
    setGovernanceMessage(null);
    setGovernanceErrorMessage(null);

    try {
      const refreshed = await getExportRequest(authToken, exportRequest.id);
      setExportRequest(refreshed);
      setGovernanceMessage("Export request status refreshed.");
    } catch {
      setGovernanceErrorMessage("Unable to refresh export request status. Try again.");
    } finally {
      setIsGovernanceSubmitting(false);
    }
  }

  async function onRequestDeletion() {
    if (!deletionConfirmChecked) {
      setGovernanceErrorMessage("Confirm deletion request before submitting.");
      return;
    }

    setIsGovernanceSubmitting(true);
    setGovernanceMessage(null);
    setGovernanceErrorMessage(null);

    try {
      const record = await createDeletionRequest(authToken, {
        idempotency_key: createIdempotencyKey("deletion"),
        mode: deletionMode,
        reason_code: "user_requested_account_deletion",
      });
      setDeletionRequest(record);
      setGovernanceMessage("Deletion request submitted.");
    } catch (error) {
      if (error instanceof GovernanceApiError && error.status === 422) {
        setGovernanceErrorMessage("Unable to submit deletion request. Check request details and try again.");
      } else {
        setGovernanceErrorMessage("Unable to submit deletion request. Try again.");
      }
    } finally {
      setIsGovernanceSubmitting(false);
    }
  }

  async function onRefreshDeletionStatus() {
    if (!deletionRequest) {
      return;
    }

    setIsGovernanceSubmitting(true);
    setGovernanceMessage(null);
    setGovernanceErrorMessage(null);

    try {
      const refreshed = await getDeletionRequest(authToken, deletionRequest.id);
      setDeletionRequest(refreshed);
      setGovernanceMessage("Deletion request status refreshed.");
    } catch {
      setGovernanceErrorMessage("Unable to refresh deletion request status. Try again.");
    } finally {
      setIsGovernanceSubmitting(false);
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
        {pushCapabilityState === "unsupported" ? (
          <p>Push is not supported in this browser. You can still manage notification preferences above.</p>
        ) : (
          <>
            <p>Permission: {pushPermission ?? "default"}</p>
            <p>Device subscription: {isPushSubscribed ? "Enabled" : "Not enabled"}</p>
            <p>Server subscription state: {pushServerStatus ?? "none"}</p>
            {pushCapabilityState === "permission_denied" ? (
              <p>Push is blocked by browser permission. Enable notifications in browser settings, then retry.</p>
            ) : null}
            {pushRecoveryAction === "resubscribe" ? (
              <p>This subscription is no longer deliverable. Recover it to continue push alerts.</p>
            ) : null}
            {pushRecoveryAction === "reactivate" ? (
              <p>This subscription is currently suppressed. Reactivate push to resume deliveries.</p>
            ) : null}
            <button
              type="button"
              onClick={onSubscribePush}
              disabled={isPushSubmitting || isPushSubscribed || pushCapabilityState === "permission_denied"}
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
            {pushRecoveryAction ? (
              <button
                type="button"
                onClick={onRecoverPush}
                disabled={isPushSubmitting || pushCapabilityState !== "subscribable"}
              >
                {pushRecoveryAction === "reactivate" ? "Reactivate push" : "Recover push subscription"}
              </button>
            ) : null}
          </>
        )}
      </section>

      <section aria-label="Data governance">
        <h2>Data governance</h2>

        <section aria-label="Data export request">
          <h3>Data export</h3>
          <p>
            Request an export of your profile, preferences, and notification history.
          </p>
          <button type="button" onClick={onRequestExport} disabled={isGovernanceSubmitting}>
            {isGovernanceSubmitting ? "Submitting..." : "Request data export"}
          </button>
          <button
            type="button"
            onClick={onRefreshExportStatus}
            disabled={isGovernanceSubmitting || !exportRequest}
          >
            Refresh export status
          </button>
          <p>
            Export request status: {exportRequest?.status ?? "not requested"}
          </p>
          {exportRequest?.completed_at ? <p>Export completed at: {exportRequest.completed_at}</p> : null}
          {exportRequest?.artifact_uri ? <p>Export artifact: {exportRequest.artifact_uri}</p> : null}
          {exportRequest?.error_code ? <p>Export error code: {exportRequest.error_code}</p> : null}
        </section>

        <section aria-label="Deletion request">
          <h3>Deletion request</h3>
          <p>Submit a deletion or anonymization request for your account data.</p>

          <label htmlFor="deletion-mode">Request mode</label>
          <select
            id="deletion-mode"
            name="deletion-mode"
            value={deletionMode}
            onChange={(event) => setDeletionMode(event.target.value as DeletionRequestMode)}
            disabled={isGovernanceSubmitting}
          >
            <option value="anonymize">Anonymize profile data</option>
            <option value="delete">Delete account data</option>
          </select>

          <label htmlFor="deletion-confirm">
            <input
              id="deletion-confirm"
              name="deletion-confirm"
              type="checkbox"
              checked={deletionConfirmChecked}
              onChange={(event) => setDeletionConfirmChecked(event.target.checked)}
              disabled={isGovernanceSubmitting}
            />
            I understand this request can remove my personal data.
          </label>

          <button type="button" onClick={onRequestDeletion} disabled={isGovernanceSubmitting}>
            {isGovernanceSubmitting ? "Submitting..." : "Request deletion"}
          </button>
          <button
            type="button"
            onClick={onRefreshDeletionStatus}
            disabled={isGovernanceSubmitting || !deletionRequest}
          >
            Refresh deletion status
          </button>
          <p>
            Deletion request status: {deletionRequest?.status ?? "not requested"}
          </p>
          <p>
            Deletion mode: {deletionRequest?.mode ?? deletionMode}
          </p>
          {deletionRequest?.due_at ? <p>Deletion due at: {deletionRequest.due_at}</p> : null}
          {deletionRequest?.completed_at ? <p>Deletion completed at: {deletionRequest.completed_at}</p> : null}
          {deletionRequest?.error_code ? <p>Deletion error code: {deletionRequest.error_code}</p> : null}
        </section>

        <LegalLinks label="Settings legal links" />
      </section>

      {successMessage ? <p role="status">{successMessage}</p> : null}
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {pushMessage ? <p role="status">{pushMessage}</p> : null}
      {pushErrorMessage ? <p role="alert">{pushErrorMessage}</p> : null}
      {governanceMessage ? (
        <p role="status">{governanceMessage}</p>
      ) : null}
      {governanceErrorMessage ? (
        <p role="alert">{governanceErrorMessage}</p>
      ) : null}
    </main>
  );
}