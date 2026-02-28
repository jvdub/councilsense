import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, submitHomeCitySelection } from "../../../lib/api/bootstrap";
import { CitySelectionForm } from "./CitySelectionForm";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    refresh: refreshMock,
  }),
}));

vi.mock("../../../lib/api/bootstrap", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/api/bootstrap")>();
  return {
    ...actual,
    submitHomeCitySelection: vi.fn(),
  };
});

describe("CitySelectionForm", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits selected city and redirects to meetings on success", async () => {
    const user = userEvent.setup();
    vi.mocked(submitHomeCitySelection).mockResolvedValue({
      user_id: "user-1",
      home_city_id: "portland-or",
      onboarding_required: false,
      supported_city_ids: ["seattle-wa", "portland-or"],
    });

    render(<CitySelectionForm authToken="token-abc" cityIds={["seattle-wa", "portland-or"]} />);

    await user.selectOptions(screen.getByLabelText("Home city"), "portland-or");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(submitHomeCitySelection).toHaveBeenCalledWith("token-abc", "portland-or");
    expect(pushMock).toHaveBeenCalledWith("/meetings");
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute(
      "href",
      "https://www.councilsense.org/privacy",
    );
    expect(screen.getByRole("link", { name: "Terms of service" })).toHaveAttribute(
      "href",
      "https://www.councilsense.org/terms",
    );
  });

  it("shows validation message when backend rejects city", async () => {
    const user = userEvent.setup();
    vi.mocked(submitHomeCitySelection).mockRejectedValue(
      new ApiError("Unsupported home_city_id", 422, "validation_error"),
    );

    render(<CitySelectionForm authToken="token-abc" cityIds={["seattle-wa"]} />);

    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Selected city is not supported.");
    expect(pushMock).not.toHaveBeenCalled();
  });
});