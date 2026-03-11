import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchBootstrap } from "./bootstrap";

const fetchMock = vi.fn<typeof fetch>();

describe("bootstrap api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches bootstrap state", async () => {
    const fixture = {
      user_id: "user-1",
      home_city_id: "city-1",
      onboarding_required: false,
      supported_city_ids: ["city-1"],
    };

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(fixture), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchBootstrap("token-abc");

    expect(result).toEqual(fixture);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v1/me/bootstrap",
      {
        method: "GET",
        headers: {
          Authorization: "Bearer token-abc",
        },
        cache: "no-store",
      },
    );
  });

  it("retries a transient network failure once before succeeding", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "user-1",
            home_city_id: null,
            onboarding_required: true,
            supported_city_ids: ["city-1"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );

    const result = await fetchBootstrap("token-abc");

    expect(result.onboarding_required).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces api errors without retrying non-retryable statuses", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "auth_required",
            message: "Authentication required",
          },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(fetchBootstrap("token-abc")).rejects.toMatchObject({
      message: "Authentication required",
      status: 401,
      code: "auth_required",
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("throws a fallback api error after exhausting network retries", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockRejectedValueOnce(new TypeError("fetch failed"));

    let thrown: unknown;
    try {
      await fetchBootstrap("token-abc");
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown).toMatchObject({
      message: "Failed to fetch bootstrap state",
      status: 0,
      code: null,
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});