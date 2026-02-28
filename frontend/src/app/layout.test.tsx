import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RootLayout from "./layout";

describe("RootLayout", () => {
  it("renders global public legal links in footer", () => {
    render(
      <RootLayout>
        <main>Example page</main>
      </RootLayout>,
    );

    expect(screen.getByLabelText("Public legal links")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute(
      "href",
      "https://www.councilsense.org/privacy",
    );
    expect(screen.getByRole("link", { name: "Terms of service" })).toHaveAttribute(
      "href",
      "https://www.councilsense.org/terms",
    );
  });
});
