import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, patchProfile } from "../../lib/api/profile";
import { SettingsPreferencesForm } from "./SettingsPreferencesForm";

const refreshMock = vi.fn();

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

describe("SettingsPreferencesForm", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.clearAllMocks();
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
});