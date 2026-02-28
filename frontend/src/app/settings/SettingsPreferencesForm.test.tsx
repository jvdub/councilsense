import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, patchProfile } from "../../lib/api/profile";
import {
  createOrRefreshPushSubscription,
  deletePushSubscription,
  listPushSubscriptions,
} from "../../lib/api/pushSubscriptions";
import { SettingsPreferencesForm } from "./SettingsPreferencesForm";

const refreshMock = vi.fn();

const serviceWorkerRegisterMock = vi.fn();
const serviceWorkerGetRegistrationMock = vi.fn();
const pushManagerGetSubscriptionMock = vi.fn();
const pushManagerSubscribeMock = vi.fn();
const pushSubscriptionUnsubscribeMock = vi.fn();
const notificationRequestPermissionMock = vi.fn();

let notificationPermissionState: NotificationPermission = "default";

function createBrowserPushSubscription(endpoint = "https://example.test/push/sub-1") {
  return {
    endpoint,
    toJSON: () => ({
      endpoint,
      keys: {
        p256dh: "p256dh-key",
        auth: "auth-key",
      },
    }),
    unsubscribe: pushSubscriptionUnsubscribeMock,
  };
}

function setPushUnsupportedBrowser() {
  Object.defineProperty(window, "PushManager", {
    configurable: true,
    value: undefined,
  });

  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: undefined,
  });

  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: undefined,
  });
}

function setPushSupportedBrowser({
  permission = "default",
  existingSubscription = null,
}: {
  permission?: NotificationPermission;
  existingSubscription?: ReturnType<typeof createBrowserPushSubscription> | null;
} = {}) {
  notificationPermissionState = permission;
  process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "BEl6MU5fM2VxQk9hYkhWVE5TV0xqU0FLeXhyY0JvUmVubEx3aUNYQnY2Q1M";

  pushManagerGetSubscriptionMock.mockResolvedValue(existingSubscription);
  pushManagerSubscribeMock.mockResolvedValue(createBrowserPushSubscription());
  serviceWorkerGetRegistrationMock.mockResolvedValue({
    pushManager: {
      getSubscription: pushManagerGetSubscriptionMock,
      subscribe: pushManagerSubscribeMock,
    },
  });
  serviceWorkerRegisterMock.mockResolvedValue({
    pushManager: {
      getSubscription: pushManagerGetSubscriptionMock,
      subscribe: pushManagerSubscribeMock,
    },
  });

  Object.defineProperty(window, "PushManager", {
    configurable: true,
    value: function PushManager() {
      return undefined;
    },
  });

  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: {
      get permission() {
        return notificationPermissionState;
      },
      requestPermission: notificationRequestPermissionMock.mockImplementation(async () => {
        notificationPermissionState = "granted";
        return "granted";
      }),
    },
  });

  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      register: serviceWorkerRegisterMock,
      getRegistration: serviceWorkerGetRegistrationMock,
    },
  });
}

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: refreshMock,
  }),
}));

vi.mock("../../lib/api/profile", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api/profile")>();
  return {
    ...actual,
    patchProfile: vi.fn(),
  };
});

vi.mock("../../lib/api/pushSubscriptions", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api/pushSubscriptions")>();
  return {
    ...actual,
    listPushSubscriptions: vi.fn(),
    createOrRefreshPushSubscription: vi.fn(),
    deletePushSubscription: vi.fn(),
  };
});

describe("SettingsPreferencesForm", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    delete process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
    setPushSupportedBrowser();
    pushSubscriptionUnsubscribeMock.mockResolvedValue(true);
    vi.mocked(listPushSubscriptions).mockResolvedValue({ items: [] });
    vi.mocked(createOrRefreshPushSubscription).mockResolvedValue({
      id: "psub-1",
      status: "active",
      failure_reason: null,
    });
    vi.mocked(deletePushSubscription).mockResolvedValue(undefined);
  });

  it("renders persisted profile values", () => {
    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa", "portland-or"]}
        initialProfile={{
          email: "user@example.com",
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(screen.getByLabelText("Home city")).toHaveValue("seattle-wa");
    expect(screen.getByLabelText("Enable notifications")).toBeChecked();
    expect(screen.getByText("Notifications paused until: Not paused")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unpause" })).toBeDisabled();
  });

  it("rehydrates persisted paused state", () => {
    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa", "portland-or"]}
        initialProfile={{
          email: "user@example.com",
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: "2026-02-28T12:00:00.000Z",
        }}
      />,
    );

    expect(screen.getByText("Notifications paused until: 2026-02-28T12:00:00.000Z")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unpause" })).toBeEnabled();
  });

  it("submits city and notification updates", async () => {
    const user = userEvent.setup();
    vi.mocked(patchProfile).mockResolvedValue({
      email: null,
      home_city_id: "portland-or",
      notifications_enabled: false,
      notifications_paused_until: null,
    });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa", "portland-or"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Home city"), "portland-or");
    await user.click(screen.getByLabelText("Enable notifications"));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(patchProfile).toHaveBeenCalledWith("token-abc", {
      home_city_id: "portland-or",
      notifications_enabled: false,
      notifications_paused_until: null,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Preferences saved.");
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("shows validation error when backend rejects payload", async () => {
    const user = userEvent.setup();
    vi.mocked(patchProfile).mockRejectedValue(
      new ApiError("Unsupported home_city_id", 422, "validation_error"),
    );

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to save preferences. Check your values and try again.",
    );
  });

  it("supports pause and unpause actions", async () => {
    const user = userEvent.setup();
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-02-27T12:00:00.000Z").getTime());

    vi.mocked(patchProfile)
      .mockResolvedValueOnce({
        email: null,
        home_city_id: "seattle-wa",
        notifications_enabled: true,
        notifications_paused_until: "2026-02-28T12:00:00.000Z",
      })
      .mockResolvedValueOnce({
        email: null,
        home_city_id: "seattle-wa",
        notifications_enabled: true,
        notifications_paused_until: null,
      });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Pause for 24 hours" }));
    expect(patchProfile).toHaveBeenNthCalledWith(1, "token-abc", {
      home_city_id: "seattle-wa",
      notifications_enabled: true,
      notifications_paused_until: "2026-02-28T12:00:00.000Z",
    });
    expect(await screen.findByText("Notifications paused until: 2026-02-28T12:00:00.000Z")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Unpause" }));
    expect(patchProfile).toHaveBeenNthCalledWith(2, "token-abc", {
      home_city_id: "seattle-wa",
      notifications_enabled: true,
      notifications_paused_until: null,
    });
    expect(await screen.findByText("Notifications paused until: Not paused")).toBeInTheDocument();
  });

  it("shows unsupported-browser push messaging", () => {
    setPushUnsupportedBrowser();

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(
      screen.getByText("Push is not supported in this browser. You can still manage notification preferences above."),
    ).toBeInTheDocument();
  });

  it("shows denied-permission guidance", () => {
    setPushSupportedBrowser({ permission: "denied" });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(
      screen.getByText("Push is blocked by browser permission. Enable notifications in browser settings, then retry."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable push on this device" })).toBeDisabled();
  });

  it("subscribes push on explicit user action", async () => {
    const user = userEvent.setup();

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Enable push on this device" }));

    expect(notificationRequestPermissionMock).toHaveBeenCalledTimes(1);
    expect(serviceWorkerRegisterMock).toHaveBeenCalledWith("/sw.js");
    expect(pushManagerSubscribeMock).toHaveBeenCalledTimes(1);
    expect(createOrRefreshPushSubscription).toHaveBeenCalledWith("token-abc", {
      endpoint: "https://example.test/push/sub-1",
      keys: {
        p256dh: "p256dh-key",
        auth: "auth-key",
      },
      user_agent: navigator.userAgent,
    });
    expect(await screen.findByText("Device subscription: Enabled")).toBeInTheDocument();
    expect(await screen.findByText("Server subscription state: active")).toBeInTheDocument();
    expect(await screen.findByText("Push enabled on this device.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable push on this device" })).toBeEnabled();
  });

  it("unsubscribes push when already subscribed", async () => {
    const user = userEvent.setup();

    vi.mocked(listPushSubscriptions).mockResolvedValue({
      items: [
        {
          id: "psub-server-1",
          endpoint: "https://example.test/push/sub-1",
          keys: {
            p256dh: "p256dh-key",
            auth: "auth-key",
          },
          status: "active",
          failure_reason: null,
          last_seen_at: "2026-02-27T12:00:00Z",
          created_at: "2026-02-27T12:00:00Z",
          updated_at: "2026-02-27T12:00:00Z",
        },
      ],
    });

    setPushSupportedBrowser({
      permission: "granted",
      existingSubscription: createBrowserPushSubscription(),
    });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(await screen.findByText("Device subscription: Enabled")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Disable push on this device" }));

    expect(pushSubscriptionUnsubscribeMock).toHaveBeenCalledTimes(1);
    expect(deletePushSubscription).toHaveBeenCalledWith("token-abc", "psub-server-1");
    expect(await screen.findByText("Device subscription: Not enabled")).toBeInTheDocument();
    expect(await screen.findByText("Server subscription state: none")).toBeInTheDocument();
    expect(await screen.findByText("Push disabled on this device.")).toBeInTheDocument();
  });

  it("maps invalid backend state to recover action", async () => {
    const user = userEvent.setup();

    vi.mocked(listPushSubscriptions).mockResolvedValue({
      items: [
        {
          id: "psub-server-invalid",
          endpoint: "https://example.test/push/sub-1",
          keys: {
            p256dh: "p256dh-key",
            auth: "auth-key",
          },
          status: "invalid",
          failure_reason: "provider_rejected",
          last_seen_at: "2026-02-27T12:00:00Z",
          created_at: "2026-02-27T12:00:00Z",
          updated_at: "2026-02-27T12:00:00Z",
        },
      ],
    });

    setPushSupportedBrowser({
      permission: "granted",
      existingSubscription: createBrowserPushSubscription(),
    });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(await screen.findByText("Server subscription state: invalid")).toBeInTheDocument();
    expect(
      await screen.findByText("This subscription is no longer deliverable. Recover it to continue push alerts."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Recover push subscription" }));

    expect(createOrRefreshPushSubscription).toHaveBeenCalled();
    expect(await screen.findByText("Push recovery completed on this device.")).toBeInTheDocument();
  });

  it("maps expired backend state to recover action", async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue({
      items: [
        {
          id: "psub-server-expired",
          endpoint: "https://example.test/push/sub-1",
          keys: {
            p256dh: "p256dh-key",
            auth: "auth-key",
          },
          status: "expired",
          failure_reason: "endpoint_expired",
          last_seen_at: "2026-02-27T12:00:00Z",
          created_at: "2026-02-27T12:00:00Z",
          updated_at: "2026-02-27T12:00:00Z",
        },
      ],
    });

    setPushSupportedBrowser({
      permission: "granted",
      existingSubscription: createBrowserPushSubscription(),
    });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(await screen.findByText("Server subscription state: expired")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recover push subscription" })).toBeInTheDocument();
  });

  it("maps suppressed backend state to reactivate action", async () => {
    const user = userEvent.setup();

    vi.mocked(listPushSubscriptions).mockResolvedValue({
      items: [
        {
          id: "psub-server-suppressed",
          endpoint: "https://example.test/push/sub-1",
          keys: {
            p256dh: "p256dh-key",
            auth: "auth-key",
          },
          status: "suppressed",
          failure_reason: "hard_failure_guardrail",
          last_seen_at: "2026-02-27T12:00:00Z",
          created_at: "2026-02-27T12:00:00Z",
          updated_at: "2026-02-27T12:00:00Z",
        },
      ],
    });

    setPushSupportedBrowser({
      permission: "granted",
      existingSubscription: createBrowserPushSubscription(),
    });

    render(
      <SettingsPreferencesForm
        authToken="token-abc"
        supportedCityIds={["seattle-wa"]}
        initialProfile={{
          email: null,
          home_city_id: "seattle-wa",
          notifications_enabled: true,
          notifications_paused_until: null,
        }}
      />,
    );

    expect(await screen.findByText("Server subscription state: suppressed")).toBeInTheDocument();
    expect(
      await screen.findByText("This subscription is currently suppressed. Reactivate push to resume deliveries."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reactivate push" }));

    expect(deletePushSubscription).toHaveBeenCalledWith("token-abc", "psub-server-suppressed");
    expect(createOrRefreshPushSubscription).toHaveBeenCalled();
    expect(await screen.findByText("Push recovery completed on this device.")).toBeInTheDocument();
  });
});