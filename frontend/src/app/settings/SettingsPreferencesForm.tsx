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
  const cardClass = "rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-lg shadow-slate-200/60 backdrop-blur sm:p-8";
  const sectionTitleClass = "text-2xl font-semibold tracking-tight text-slate-950";
  const helperTextClass = "text-sm leading-6 text-slate-600";
  const selectClass = "mt-2 block w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100 disabled:cursor-not-allowed disabled:bg-slate-100";
  const checkboxClass = "h-4 w-4 rounded border-slate-300 text-cyan-700 focus:ring-cyan-500";
  const secondaryButtonClass = "inline-flex items-center justify-center rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400";
  const primaryButtonClass = "inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400";
  const infoRowClass = "rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700";
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
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 lg:gap-8">
      <section className="rounded-[2rem] border border-slate-200/80 bg-slate-950 px-6 py-8 text-white shadow-2xl shadow-slate-400/20 sm:px-8">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-200">Resident controls</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">Settings</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">
          Manage your home city, alerts, push subscriptions, and data governance requests in one place.
        </p>
      </section>

      <section className={cardClass}>
        <div className="space-y-2">
          <h2 className={sectionTitleClass}>Preferences</h2>
          <p className={helperTextClass}>Choose your primary city and how CouncilSense should contact you.</p>
        </div>

        <form onSubmit={onSubmit} className="mt-8 space-y-6">
          <div>
            <label htmlFor="home-city" className="block text-sm font-medium text-slate-700">Home city</label>
        <select
          id="home-city"
          name="home-city"
          value={homeCityId}
          onChange={(event) => setHomeCityId(event.target.value)}
          disabled={isSubmitting}
          className={selectClass}
        >
          <option value="">Select a city</option>
          {cityOptions.map((option) => (
            <option key={option.cityId} value={option.cityId}>
              {option.label}
            </option>
          ))}
        </select>
          </div>

          <label htmlFor="notifications-enabled" className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm font-medium text-slate-700">
            <input
            id="notifications-enabled"
            name="notifications-enabled"
            type="checkbox"
            checked={notificationsEnabled}
            onChange={(event) => setNotificationsEnabled(event.target.checked)}
            disabled={isSubmitting}
            className={checkboxClass}
          />
          Enable notifications
          </label>

          <p className={infoRowClass}>
          Notifications paused until: {notificationsPausedUntil ?? "Not paused"}
          </p>

          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={onPauseFor24Hours} disabled={isSubmitting} className={secondaryButtonClass}>
          Pause for 24 hours
            </button>
            <button
              type="button"
              onClick={onUnpause}
              disabled={isSubmitting || notificationsPausedUntil === null}
              className={secondaryButtonClass}
            >
          Unpause
            </button>

            <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? "Saving..." : "Save preferences"}
            </button>
          </div>
        </form>
      </section>

      <section aria-label="Push notifications" className={cardClass}>
        <div className="space-y-2">
          <h2 className={sectionTitleClass}>Push notifications</h2>
          <p className={helperTextClass}>Manage browser-based alerts for the device you are using right now.</p>
        </div>
        {pushCapabilityState === "unsupported" ? (
          <p className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">Push is not supported in this browser. You can still manage notification preferences above.</p>
        ) : (
          <div className="mt-6 space-y-4">
            <p className={infoRowClass}>Permission: {pushPermission ?? "default"}</p>
            <p className={infoRowClass}>Device subscription: {isPushSubscribed ? "Enabled" : "Not enabled"}</p>
            <p className={infoRowClass}>Server subscription state: {pushServerStatus ?? "none"}</p>
            {pushCapabilityState === "permission_denied" ? (
              <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">Push is blocked by browser permission. Enable notifications in browser settings, then retry.</p>
            ) : null}
            {pushRecoveryAction === "resubscribe" ? (
              <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">This subscription is no longer deliverable. Recover it to continue push alerts.</p>
            ) : null}
            {pushRecoveryAction === "reactivate" ? (
              <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">This subscription is currently suppressed. Reactivate push to resume deliveries.</p>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onSubscribePush}
                disabled={isPushSubmitting || isPushSubscribed || pushCapabilityState === "permission_denied"}
                className={primaryButtonClass}
              >
              {isPushSubmitting ? "Updating push..." : "Enable push on this device"}
              </button>
              <button
                type="button"
                onClick={onUnsubscribePush}
                disabled={isPushSubmitting || !isPushSubscribed}
                className={secondaryButtonClass}
              >
              Disable push on this device
              </button>
            {pushRecoveryAction ? (
              <button
                type="button"
                onClick={onRecoverPush}
                disabled={isPushSubmitting || pushCapabilityState !== "subscribable"}
                className={secondaryButtonClass}
              >
                {pushRecoveryAction === "reactivate" ? "Reactivate push" : "Recover push subscription"}
              </button>
            ) : null}
            </div>
          </div>
        )}
      </section>

      <section aria-label="Data governance" className={cardClass}>
        <div className="space-y-2">
          <h2 className={sectionTitleClass}>Data governance</h2>
          <p className={helperTextClass}>Request exports and account deletion actions with clear status tracking.</p>
        </div>

        <div className="mt-8 grid gap-6 xl:grid-cols-2">
          <section aria-label="Data export request" className="rounded-3xl border border-slate-200 bg-slate-50/80 p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">Data export</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
            Request an export of your profile, preferences, and notification history.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={onRequestExport} disabled={isGovernanceSubmitting} className={primaryButtonClass}>
            {isGovernanceSubmitting ? "Submitting..." : "Request data export"}
              </button>
              <button
                type="button"
                onClick={onRefreshExportStatus}
                disabled={isGovernanceSubmitting || !exportRequest}
                className={secondaryButtonClass}
              >
            Refresh export status
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <p className={infoRowClass}>
            Export request status: {exportRequest?.status ?? "not requested"}
              </p>
              {exportRequest?.completed_at ? <p className={infoRowClass}>Export completed at: {exportRequest.completed_at}</p> : null}
              {exportRequest?.artifact_uri ? <p className={infoRowClass}>Export artifact: {exportRequest.artifact_uri}</p> : null}
              {exportRequest?.error_code ? <p className={infoRowClass}>Export error code: {exportRequest.error_code}</p> : null}
            </div>
          </section>

          <section aria-label="Deletion request" className="rounded-3xl border border-slate-200 bg-slate-50/80 p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">Deletion request</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">Submit a deletion or anonymization request for your account data.</p>

            <div className="mt-4">
              <label htmlFor="deletion-mode" className="block text-sm font-medium text-slate-700">Request mode</label>
              <select
                id="deletion-mode"
                name="deletion-mode"
                value={deletionMode}
                onChange={(event) => setDeletionMode(event.target.value as DeletionRequestMode)}
                disabled={isGovernanceSubmitting}
                className={selectClass}
              >
                <option value="anonymize">Anonymize profile data</option>
                <option value="delete">Delete account data</option>
              </select>
            </div>

            <label htmlFor="deletion-confirm" className="mt-4 flex items-start gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-700">
              <input
              id="deletion-confirm"
              name="deletion-confirm"
              type="checkbox"
              checked={deletionConfirmChecked}
              onChange={(event) => setDeletionConfirmChecked(event.target.checked)}
              disabled={isGovernanceSubmitting}
              className={`${checkboxClass} mt-0.5`}
            />
            I understand this request can remove my personal data.
            </label>

            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={onRequestDeletion} disabled={isGovernanceSubmitting} className={primaryButtonClass}>
            {isGovernanceSubmitting ? "Submitting..." : "Request deletion"}
              </button>
              <button
                type="button"
                onClick={onRefreshDeletionStatus}
                disabled={isGovernanceSubmitting || !deletionRequest}
                className={secondaryButtonClass}
              >
            Refresh deletion status
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <p className={infoRowClass}>
            Deletion request status: {deletionRequest?.status ?? "not requested"}
              </p>
              <p className={infoRowClass}>
            Deletion mode: {deletionRequest?.mode ?? deletionMode}
              </p>
              {deletionRequest?.due_at ? <p className={infoRowClass}>Deletion due at: {deletionRequest.due_at}</p> : null}
              {deletionRequest?.completed_at ? <p className={infoRowClass}>Deletion completed at: {deletionRequest.completed_at}</p> : null}
              {deletionRequest?.error_code ? <p className={infoRowClass}>Deletion error code: {deletionRequest.error_code}</p> : null}
            </div>
          </section>
        </div>

        <div className="mt-8 border-t border-slate-200 pt-6">
          <LegalLinks label="Settings legal links" />
        </div>
      </section>

      {successMessage ? <p role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-700">{successMessage}</p> : null}
      {errorMessage ? <p role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">{errorMessage}</p> : null}
      {pushMessage ? <p role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-700">{pushMessage}</p> : null}
      {pushErrorMessage ? <p role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">{pushErrorMessage}</p> : null}
      {governanceMessage ? (
        <p role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-700">{governanceMessage}</p>
      ) : null}
      {governanceErrorMessage ? (
        <p role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">{governanceErrorMessage}</p>
      ) : null}
    </main>
  );
}