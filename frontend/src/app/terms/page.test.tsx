import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import TermsOfServicePage from "./page";

describe("TermsOfServicePage", () => {
  it("renders terms content with local navigation", () => {
    render(<TermsOfServicePage />);

    expect(
      screen.getByRole("heading", { name: "Terms of service" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /provides meeting summaries, evidence references, and settings controls/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Review privacy policy" }),
    ).toHaveAttribute("href", "/privacy");
  });
});
