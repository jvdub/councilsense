import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "./baseUrl";

describe("api base url resolution", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.API_INTERNAL_BASE_URL;
    vi.unstubAllGlobals();
  });

  it("uses the current browser hostname by default", () => {
    vi.stubGlobal("window", {
      location: {
        hostname: "127.0.0.1",
        protocol: "http:",
      },
    });

    expect(getApiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("prefers the public browser override when provided", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test";
    vi.stubGlobal("window", {
      location: {
        hostname: "127.0.0.1",
        protocol: "http:",
      },
    });

    expect(getApiBaseUrl()).toBe("https://api.example.test");
  });

  it("preserves the internal server-side fallback chain", () => {
    vi.stubGlobal("window", undefined);
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://public.example.test";
    process.env.API_INTERNAL_BASE_URL = "http://internal.example.test:8000";

    expect(getApiBaseUrl()).toBe("http://internal.example.test:8000");
  });

  it("uses the default internal api base url on the server when no overrides are set", () => {
    vi.stubGlobal("window", undefined);

    expect(getApiBaseUrl()).toBe("http://api:8000");
  });
});