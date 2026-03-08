import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "./baseUrl";

const originalNodeEnv = process.env.NODE_ENV;
const originalRuntimeEnv = process.env.COUNCILSENSE_RUNTIME_ENV;

describe("api base url resolution", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.API_INTERNAL_BASE_URL;
    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV;
    } else {
      process.env.NODE_ENV = originalNodeEnv;
    }
    if (originalRuntimeEnv === undefined) {
      delete process.env.COUNCILSENSE_RUNTIME_ENV;
    } else {
      process.env.COUNCILSENSE_RUNTIME_ENV = originalRuntimeEnv;
    }
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

  it("uses the local api fallback on the server during direct development runs", () => {
    vi.stubGlobal("window", undefined);
    process.env.NODE_ENV = "development";

    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("uses the local api fallback on the server for explicit local runtime env", () => {
    vi.stubGlobal("window", undefined);
    process.env.COUNCILSENSE_RUNTIME_ENV = "local";

    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("uses the default internal api base url on the server when no overrides are set", () => {
    vi.stubGlobal("window", undefined);
    process.env.NODE_ENV = "production";
    delete process.env.COUNCILSENSE_RUNTIME_ENV;

    expect(getApiBaseUrl()).toBe("http://api:8000");
  });
});