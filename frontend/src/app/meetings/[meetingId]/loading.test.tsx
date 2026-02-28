import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MeetingDetailLoading from "./loading";

describe("MeetingDetailLoading", () => {
  it("renders a loading state for meeting detail", () => {
    render(<MeetingDetailLoading />);

    expect(screen.getByRole("heading", { name: "Meeting detail" })).toBeInTheDocument();
    expect(screen.getByText("Loading meeting detail…")).toBeInTheDocument();
  });
});
