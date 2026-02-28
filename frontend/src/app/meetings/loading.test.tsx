import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MeetingsLoading from "./loading";

describe("MeetingsLoading", () => {
  it("renders a loading state for meetings", () => {
    render(<MeetingsLoading />);

    expect(screen.getByRole("heading", { name: "Meetings" })).toBeInTheDocument();
    expect(screen.getByText("Loading meetings…")).toBeInTheDocument();
  });
});
