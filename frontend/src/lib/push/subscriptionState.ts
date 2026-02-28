import type { PushSubscriptionServerStatus } from "../api/pushSubscriptions";

export type BrowserPermissionState = "granted" | "denied" | "default";

export type PushCapabilityState = "unsupported" | "permission_required" | "permission_denied" | "subscribable";

export type PushRecoveryAction = "resubscribe" | "reactivate" | null;

export function mapPushCapabilityState(
  isPushSupported: boolean,
  pushPermission: BrowserPermissionState | null,
): PushCapabilityState {
  if (!isPushSupported) {
    return "unsupported";
  }

  if (pushPermission === "denied") {
    return "permission_denied";
  }

  if (pushPermission === "default" || pushPermission === null) {
    return "permission_required";
  }

  return "subscribable";
}

export function mapPushRecoveryAction(status: PushSubscriptionServerStatus | null): PushRecoveryAction {
  if (status === "suppressed") {
    return "reactivate";
  }

  if (status === "invalid" || status === "expired") {
    return "resubscribe";
  }

  return null;
}