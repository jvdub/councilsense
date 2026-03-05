import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import LandingPage from "./page";

describe("LandingPage", () => {
  it("renders a link to the meetings flow", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", { name: "CouncilSense" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to meetings" }),
    ).toHaveAttribute("href", "/meetings");
  });
});
