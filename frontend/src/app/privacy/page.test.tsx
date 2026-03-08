import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import PrivacyPolicyPage from "./page";

describe("PrivacyPolicyPage", () => {
  it("renders privacy content with local navigation", () => {
    render(<PrivacyPolicyPage />);

    expect(screen.getByRole("heading", { name: "Privacy policy" })).toBeInTheDocument();
    expect(
      screen.getByText(/stores account, city preference, and notification settings/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review terms of service" })).toHaveAttribute(
      "href",
      "/terms",
    );
  });
});